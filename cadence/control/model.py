import difflib
import re
from collections.abc import Mapping
from typing import Any

from cadence.control.recall import through
from cadence.control.region import BEGIN, END, splice, split
from cadence.core.dto import Directive, Proposal, Suggestion
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


IMPROVE = """\
You are improving a program.

The current program:
{code}

What to try:
{hint}{guidance}

Reply with a unified diff inside a ```diff fenced block, and nothing else.\
"""

REWRITE = """\
You are improving a program.

The current program:
{code}

What to try:
{hint}{guidance}

Reply with the complete new program inside a ```python fenced block, and
nothing else. Include every line, even the ones you did not change.\
"""

REGION = """\
You are improving one part of a program. The whole program is shown so you
have context, but you may only change what lies between the markers.

{code}

What to try:
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
    ) -> None:
        if template not in TEMPLATES:
            raise KeyError(f"no template named {template!r}")
        self.backend = backend
        self.template = template
        self.guidance = guidance
        self.calls = calls
        self.markers = markers

    def recipe(self, directive: Directive) -> Mapping[str, Any]:
        # Guidance is part of the recipe, not an extra applied afterwards:
        # rebuilding the prompt from the recipe has to reproduce it exactly.
        return {
            "template": self.template,
            "code": directive.code,
            "hint": hint_for(directive.index),
            "guidance": _guidance_block(self.guidance),
        }

    def propose(self, directive: Directive, key: str | None = None) -> Suggestion:
        recipe = self.recipe(directive)
        prompt = render(recipe)
        if self.calls is None or key is None:
            completion, replayed = self._ask(prompt), False
        else:
            completion, replayed = through(
                self.calls, key, prompt, lambda: self._ask(prompt)
            )
        proposal = Proposal(
            patch=self._patch(directive.code, completion.text),
            prompt=prompt,
            recipe=recipe,
            raw_response=completion.text,
        )
        return Suggestion(proposal, completion, replayed)

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

    def _ask(self, prompt: str):
        return self.backend.call(prompt)
