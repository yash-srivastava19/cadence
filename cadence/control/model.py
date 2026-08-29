import difflib
import re
from collections.abc import Mapping
from typing import Any

from cadence.control.recall import digest, through
from cadence.control.region import BEGIN, END, splice, split
from cadence.core.dto import Completion, Directive, Proposal, Request, Suggestion
from cadence.core.ports import Backend, Calls
from cadence.errors import PatchError

__all__ = [
    "HINTS",
    "TEMPLATES",
    "Model",
    "hint_for",
    "parse_patch",
    "parse_program",
    "render",
]

GUIDANCE = """

What matters here, from the person who wrote this:
{guidance}\
"""  # joined directly onto {hint}, so an empty guidance leaves no gap


STANDING = """\
How the program above scored:
{rows}

"""

UNMEASURED = """\
Nobody has scored the program above yet. It is where the search starts.

"""

PROBLEM = """\
Your last reply could not be used: {problem}
Read that before answering -- the same mistake again costs another attempt
and the trial is abandoned when they run out.

"""


IMPROVE = """\
You are improving a program.

The current program:
{code}

{standing}{problem}What to try:
{hint}{guidance}

Reply with a unified diff inside a ```diff fenced block, and nothing else.\
"""

REWRITE = """\
You are improving a program.

The current program:
{code}

{standing}{problem}What to try:
{hint}{guidance}

Reply with the complete new program inside a ```python fenced block, and
nothing else. Include every line, even the ones you did not change.\
"""

REGION = """\
You are improving one part of a program. The whole program is shown so you
have context, but you may only change what lies between the markers.

{code}

{standing}{problem}What to try:
{hint}{guidance}

Reply with the replacement for the marked section only, inside a ```python
fenced block. Do not include the marker lines themselves, and do not change
anything outside them.\
"""

#: What to try next, rotated by trial index. Prompt content, so it lives with
#: the templates: a search method should not have to carry English around to
#: be swapped out, and tuning these should not mean editing an algorithm.
HINTS = (
    "make it faster without changing what it returns",
    "handle the case the current code ignores",
    "replace the inner loop with something cheaper",
    "try a different strategy entirely",
)


def hint_for(index: int) -> str:
    return HINTS[index % len(HINTS)]


TEMPLATES: Mapping[str, str] = {
    "improve": IMPROVE,
    "rewrite": REWRITE,
    "region": REGION,
}
WHOLE = {"rewrite", "region"}

DIFF_BLOCK = re.compile(r"```diff\n(?P<body>.*?)```", re.DOTALL)
CODE_BLOCK = re.compile(r"```(?:python)?\n(?P<body>.*?)```", re.DOTALL)


def _guidance_block(guidance: str | None) -> str:
    if guidance is None or not guidance.strip():
        return ""
    return GUIDANCE.format(guidance=guidance.strip())


#: How a metric direction reads to whoever has to improve it.
BETTER = {"maximize": "higher is better", "minimize": "lower is better"}


def _standing_block(
    standing: Mapping[str, float] | None, goals: Mapping[str, str]
) -> str:
    """What the parent scored, and which way is up.

    The direction is the whole reason the manifest's metrics reach this file.
    "ms = 0.698" tells a model nothing it can act on; "ms = 0.698 (lower is
    better)" tells it what improving means, which is the one thing it cannot
    work out from the program in front of it.
    """
    if not standing:
        return UNMEASURED
    rows = "\n".join(
        f"  {name} = {value:g}{_aim(name, goals)}"
        for name, value in sorted(standing.items())
    )
    return STANDING.format(rows=rows)


def _aim(name: str, goals: Mapping[str, str]) -> str:
    direction = BETTER.get(goals.get(name, ""))
    return f"   ({direction})" if direction else ""


def _problem_block(problem: str | None) -> str:
    if problem is None or not problem.strip():
        return ""
    return PROBLEM.format(problem=problem.strip())


def render(recipe: Mapping[str, Any]) -> str:
    ingredients = dict(recipe)
    template = TEMPLATES[ingredients.pop("template")]
    return template.format(**ingredients)


def parse_patch(text: str) -> tuple[str, ...]:
    block = DIFF_BLOCK.search(text)
    if block is None:
        raise PatchError("the response has no closed ```diff block")
    lines = tuple(block["body"].strip("\n").splitlines())
    if not any(line.strip() for line in lines):
        raise PatchError("the ```diff block is empty")
    return lines


def parse_program(text: str) -> str:
    block = CODE_BLOCK.search(text)
    if block is None:
        raise PatchError("the response has no closed ```python block")
    program = block["body"].strip("\n")
    if not program.strip():
        raise PatchError("the ```python block is empty")
    return program


def as_patch(before: str, after: str) -> tuple[str, ...]:
    body = difflib.unified_diff(_lines(before), _lines(after), "a/program", "b/program")
    return tuple("".join(body).splitlines())


def _lines(text: str) -> list[str]:
    return (text if text.endswith("\n") else text + "\n").splitlines(True)


class Model:
    def __init__(
        self,
        backend: Backend,
        template: str = "region",
        guidance: str | None = None,
        calls: Calls | None = None,
        markers: tuple[str, str] = (BEGIN, END),
        goals: Mapping[str, str] | None = None,
    ) -> None:
        if template not in TEMPLATES:
            raise KeyError(f"no template named {template!r}")
        self.backend = backend
        self.template = template
        self.guidance = guidance
        self.calls = calls
        self.markers = markers
        # Which way is better, per metric, from the manifest. Configuration
        # like the template and the guidance are -- a search method should not
        # have to carry it, and it is not a fact about any one parent.
        self.goals = dict(goals or {})

    def recipe(
        self, directive: Directive, problem: str | None = None
    ) -> Mapping[str, Any]:
        # Every input to the prompt is in here, not applied afterwards:
        # rebuilding the prompt from the recipe has to reproduce it exactly,
        # or a replayed call answers a question we are no longer asking.
        return {
            "template": self.template,
            "code": directive.code,
            "standing": _standing_block(directive.standing, self.goals),
            "problem": _problem_block(problem),
            "hint": hint_for(directive.index),
            "guidance": _guidance_block(self.guidance),
        }

    def prepare(
        self, directive: Directive, key: str = "", problem: str | None = None
    ) -> Request:
        """Everything about the call that costs nothing.

        Separate from send() so a caller can write down what it is about to do
        before doing it. Pure: called twice with the same directive it builds
        the same request byte for byte, which is what makes the recipe worth
        storing at all.
        """
        recipe = self.recipe(directive, problem)
        prompt = render(recipe)
        return Request(
            key=key or "unkeyed",
            prompt=prompt,
            digest=digest(prompt),
            template_hash=digest(TEMPLATES[self.template]),
            recipe=recipe,
        )

    def ask(self, request: Request) -> tuple[Completion, bool]:
        """The billed step, and only that.

        Separate from reading the answer because a reply that cannot be
        parsed was still paid for: a caller counting what a run spends has to
        count it here, before anything can go wrong with what came back.
        """
        if self.calls is None:
            return self._ask(request), False
        return through(
            self.calls,
            request.key,
            request.prompt,
            lambda: self._ask(request),
        )

    def read(self, request: Request, completion: Completion, code: str) -> Proposal:
        """What we made of the answer. Free, and where it may be refused."""
        return Proposal(
            patch=self._patch(code, completion.text),
            prompt=request.prompt,
            recipe=request.recipe,
            raw_response=completion.text,
        )

    def send(self, request: Request, code: str) -> Suggestion:
        completion, replayed = self.ask(request)
        proposal = self.read(request, completion, code)
        return Suggestion(proposal, completion, replayed, request.key)

    def propose(self, directive: Directive, key: str | None = None) -> Suggestion:
        """prepare then send, for a caller with nothing to write down."""
        return self.send(self.prepare(directive, key or ""), directive.code)

    def _patch(self, before: str, answer: str) -> tuple[str, ...]:
        if self.template not in WHOLE:
            return parse_patch(answer)
        written = parse_program(answer)
        marked = split(before, *self.markers)
        after = splice(before, written, *self.markers) if marked else written
        patch = as_patch(before, after)
        if not patch:
            raise PatchError("the program came back unchanged")
        return patch

    def _ask(self, request: Request):
        return self.backend.call(request)
