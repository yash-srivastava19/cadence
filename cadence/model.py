import re
from collections.abc import Mapping
from typing import Any, NamedTuple

from cadence.backends import Backend, Completion
from cadence.exceptions import PatchError, RetryableModelError
from cadence.interfaces import Directive
from cadence.verdict import Proposal

__all__ = ["TEMPLATES", "render", "parse_patch", "Suggestion", "Model"]

IMPROVE = """\
You are improving a program.

The current program:
{code}

What to try:
{hint}

Reply with a unified diff inside a ```diff fenced block, and nothing else.\
"""

TEMPLATES: Mapping[str, str] = {"improve": IMPROVE}

DIFF_BLOCK = re.compile(r"```diff\n(?P<body>.*?)```", re.DOTALL)


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


class Suggestion(NamedTuple):
    proposal: Proposal
    completion: Completion


class Model:
    def __init__(
        self, backend: Backend, template: str = "improve", attempts: int = 3
    ) -> None:
        if template not in TEMPLATES:
            raise KeyError(f"no template named {template!r}")
        self.backend = backend
        self.template = template
        self.attempts = attempts

    def recipe(self, directive: Directive) -> Mapping[str, Any]:
        return {
            "template": self.template,
            "code": directive.code,
            "hint": directive.hint,
        }

    def propose(self, directive: Directive) -> Suggestion:
        recipe = self.recipe(directive)
        prompt = render(recipe)
        completion = self._ask(prompt)
        proposal = Proposal(
            patch=parse_patch(completion.text),
            prompt=prompt,
            recipe=recipe,
            raw_response=completion.text,
        )
        return Suggestion(proposal, completion)

    def _ask(self, prompt: str):
        for attempt in range(1, self.attempts + 1):
            try:
                return self.backend.call(prompt)
            except RetryableModelError:
                if attempt == self.attempts:
                    raise
        raise AssertionError
