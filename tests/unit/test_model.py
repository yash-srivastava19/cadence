import pytest
from pydantic import ValidationError

from cadence.backends import Scripted
from cadence.exceptions import PatchError, RetryableModelError, TerminalModelError
from cadence.interfaces import Directive
from cadence.model import Model, parse_patch, render

PATCH = """\
--- a/solve.py
+++ b/solve.py
@@ -1,2 +1,2 @@
-    return []
+    return greedy(items)\
"""

ANSWER = f"Here is my change:\n\n```diff\n{PATCH}\n```\n"


def a_directive(hint="try a greedy pass"):
    return Directive(parent="abc123", code="def solve(): return []", hint=hint)


def a_model(*responses):
    return Model(backend=Scripted(*responses))


class TestParsingAPatch:
    def test_it_finds_the_diff_block(self):
        assert parse_patch(ANSWER)[0] == "--- a/solve.py"

    def test_it_keeps_every_line(self):
        assert len(parse_patch(ANSWER)) == len(PATCH.splitlines())

    def test_prose_around_the_block_is_dropped(self):
        assert "Here is my change:" not in parse_patch(ANSWER)

    def test_a_response_with_no_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="no ```diff block"):
            parse_patch("I would change the loop, but here is prose instead.")

    def test_an_unclosed_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="never closed"):
            parse_patch("```diff\n--- a/x\n")

    def test_an_empty_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="empty"):
            parse_patch("```diff\n\n```")


class TestTheRecipeRebuildsThePrompt:
    def test_rendering_the_recipe_reproduces_the_prompt(self):
        model = a_model(ANSWER)
        proposal = model.propose(a_directive())
        assert render(proposal.recipe) == proposal.prompt

    def test_the_prompt_carries_the_parent_code(self):
        proposal = a_model(ANSWER).propose(a_directive())
        assert "def solve(): return []" in proposal.prompt

    def test_the_prompt_carries_the_hint(self):
        proposal = a_model(ANSWER).propose(a_directive(hint="use a heap"))
        assert "use a heap" in proposal.prompt

    def test_a_different_hint_gives_a_different_prompt(self):
        first = a_model(ANSWER).propose(a_directive(hint="one"))
        second = a_model(ANSWER).propose(a_directive(hint="two"))
        assert first.prompt != second.prompt

    def test_an_unknown_template_is_refused_at_construction(self):
        with pytest.raises(KeyError):
            Model(backend=Scripted(), template="nonexistent")


class TestProposing:
    def test_it_returns_the_parsed_patch(self):
        proposal = a_model(ANSWER).propose(a_directive())
        assert proposal.patch[0] == "--- a/solve.py"

    def test_it_keeps_the_raw_response(self):
        proposal = a_model(ANSWER).propose(a_directive())
        assert proposal.raw_response == ANSWER

    def test_it_sends_the_prompt_it_recorded(self):
        model = a_model(ANSWER)
        proposal = model.propose(a_directive())
        assert model.backend.prompts == [proposal.prompt]

    def test_an_unparseable_answer_raises_rather_than_returning_nothing(self):
        with pytest.raises(PatchError):
            a_model("no diff here").propose(a_directive())


class TestRetryClassification:
    def test_a_retryable_error_is_retried(self):
        model = a_model(RetryableModelError("429"), ANSWER)
        proposal = model.propose(a_directive())
        assert proposal.patch[0] == "--- a/solve.py"
        assert len(model.backend.prompts) == 2

    def test_it_gives_up_after_the_attempt_budget(self):
        model = Model(
            backend=Scripted(*[RetryableModelError("429")] * 3),
            attempts=3,
        )
        with pytest.raises(RetryableModelError):
            model.propose(a_directive())
        assert len(model.backend.prompts) == 3

    def test_a_terminal_error_is_not_retried(self):
        model = a_model(TerminalModelError("401"), ANSWER)
        with pytest.raises(TerminalModelError):
            model.propose(a_directive())
        assert len(model.backend.prompts) == 1


class TestADirective:
    def test_it_cannot_be_edited(self):
        directive = a_directive()
        with pytest.raises(ValidationError):
            directive.hint = "something else"

    def test_it_refuses_a_blank_hint(self):
        with pytest.raises(ValidationError):
            Directive(parent="abc", code="x = 1", hint="  ")

    def test_it_survives_json(self):
        directive = a_directive()
        assert Directive.model_validate_json(directive.model_dump_json()) == directive
