from collections.abc import Mapping
from typing import Any

from cadence.backends import Backend
from cadence.exceptions import PatchError, RetryableModelError
from cadence.interfaces import Directive
from cadence.verdict import Proposal

__all__ = ["TEMPLATES", "render", "parse_patch", "Model"]

IMPROVE = """\
You are improving a program.

The current program:
{code}

What to try:
{hint}

Reply with a unified diff inside a ```diff fenced block, and nothing else.\
"""

TEMPLATES: Mapping[str, str] = {"improve": IMPROVE}

FENCE = "```"


def render(recipe: Mapping[str, Any]) -> str:
    ingredients = dict(recipe)
    template = TEMPLATES[ingredients.pop("template")]
    return template.format(**ingredients)


def parse_patch(text: str) -> tuple[str, ...]:
    opening = f"{FENCE}diff"
    start = text.find(opening)
    if start < 0:
        raise PatchError("the response has no ```diff block")
    body = text[start + len(opening) :]
    end = body.find(FENCE)
    if end < 0:
        raise PatchError("the ```diff block is never closed")
    lines = tuple(line for line in body[:end].strip("\n").splitlines())
    if not any(line.strip() for line in lines):
        raise PatchError("the ```diff block is empty")
    return lines


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

    def propose(self, directive: Directive) -> Proposal:
        recipe = self.recipe(directive)
        prompt = render(recipe)
        completion = self._ask(prompt)
        return Proposal(
            patch=parse_patch(completion.text),
            prompt=prompt,
            recipe=recipe,
            raw_response=completion.text,
        )

    def _ask(self, prompt: str):
        for attempt in range(1, self.attempts + 1):
            try:
                return self.backend.call(prompt)
            except RetryableModelError:
                if attempt == self.attempts:
                    raise
        raise AssertionError
