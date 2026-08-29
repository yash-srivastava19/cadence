import pytest
from pydantic import ValidationError

from cadence.control.backends import Scripted
from cadence.control.model import Model, hint_for, parse_patch, render
from cadence.core.dto import Directive
from cadence.errors import PatchError, TerminalModelError

PATCH = """\
--- a/solve.py
+++ b/solve.py
@@ -1,2 +1,2 @@
-    return []
+    return greedy(items)\
"""

ANSWER = f"Here is my change:\n\n```diff\n{PATCH}\n```\n"


def a_directive(index=0):
    return Directive(parent="abc123", code="def solve(): return []", index=index)


def a_model(*responses, template="improve"):
    return Model(backend=Scripted(*responses), template=template)


class TestParsingAPatch:
    def test_it_finds_the_diff_block(self):
        assert parse_patch(ANSWER)[0] == "--- a/solve.py"

    def test_it_keeps_every_line(self):
        assert len(parse_patch(ANSWER)) == len(PATCH.splitlines())

    def test_prose_around_the_block_is_dropped(self):
        assert "Here is my change:" not in parse_patch(ANSWER)

    def test_a_response_with_no_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="```diff block"):
            parse_patch("I would change the loop, but here is prose instead.")

    def test_an_unclosed_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="```diff block"):
            parse_patch("```diff\n--- a/x\n")

    def test_an_empty_block_is_a_patch_error(self):
        with pytest.raises(PatchError, match="empty"):
            parse_patch("```diff\n\n```")


class TestTheRecipeRebuildsThePrompt:
    def test_rendering_the_recipe_reproduces_the_prompt(self):
        model = a_model(ANSWER)
        proposal = model.propose(a_directive()).proposal
        assert render(proposal.recipe) == proposal.prompt

    def test_the_prompt_carries_the_parent_code(self):
        proposal = a_model(ANSWER).propose(a_directive()).proposal
        assert "def solve(): return []" in proposal.prompt

    def test_the_prompt_carries_the_hint_for_that_trial(self):
        proposal = a_model(ANSWER).propose(a_directive(index=1)).proposal
        assert hint_for(1) in proposal.prompt

    def test_a_different_hint_gives_a_different_prompt(self):
        first = a_model(ANSWER).propose(a_directive(index=0)).proposal
        second = a_model(ANSWER).propose(a_directive(index=1)).proposal
        assert first.prompt != second.prompt

    def test_an_unknown_template_is_refused_at_construction(self):
        with pytest.raises(KeyError):
            Model(backend=Scripted(), template="nonexistent")


class TestAskingForTheWholeProgram:
    def test_the_diff_is_computed_from_what_came_back(self):
        answer = "```python\ndef solve(): return 1\n```"
        proposal = a_model(answer, template="rewrite").propose(a_directive()).proposal
        assert "+def solve(): return 1" in proposal.patch

    def test_the_computed_diff_applies(self):
        from cadence.control.patcher import apply_patch

        answer = "```python\ndef solve(): return 1\n```"
        directive = a_directive()
        proposal = a_model(answer, template="rewrite").propose(directive).proposal
        assert apply_patch(directive.code, proposal.patch) == "def solve(): return 1"

    def test_an_unchanged_program_is_refused(self):
        directive = a_directive()
        answer = f"```python\n{directive.code}\n```"
        with pytest.raises(PatchError, match="unchanged"):
            a_model(answer, template="rewrite").propose(directive)

    def test_prose_with_no_block_is_refused(self):
        with pytest.raises(PatchError, match="```python block"):
            a_model("I would rewrite it entirely.", template="rewrite").propose(
                a_directive()
            )

    def test_only_the_marked_region_is_replaced(self):
        from cadence.control.patcher import apply_patch
        from cadence.core.dto import Directive

        marked = "before = 1\n# CADENCE:BEGIN\nx = 1\n# CADENCE:END\nafter = 2\n"
        directive = Directive(parent="p", code=marked)
        proposal = (
            a_model("```python\nx = 99\n```", template="region")
            .propose(directive)
            .proposal
        )
        after = apply_patch(marked, proposal.patch)
        assert "x = 99" in after
        assert after.startswith("before = 1")
        assert after.rstrip().endswith("after = 2")


class TestProposing:
    def test_it_returns_the_parsed_patch(self):
        proposal = a_model(ANSWER).propose(a_directive()).proposal
        assert proposal.patch[0] == "--- a/solve.py"

    def test_it_keeps_the_raw_response(self):
        proposal = a_model(ANSWER).propose(a_directive()).proposal
        assert proposal.raw_response == ANSWER

    def test_it_sends_the_prompt_it_recorded(self):
        model = a_model(ANSWER)
        proposal = model.propose(a_directive()).proposal
        assert model.backend.prompts == [proposal.prompt]

    def test_an_unparseable_answer_raises_rather_than_returning_nothing(self):
        with pytest.raises(PatchError):
            _ = a_model("no diff here").propose(a_directive()).proposal


class TestRetryClassification:
    def test_a_terminal_error_is_not_retried(self):
        model = a_model(TerminalModelError("401"), ANSWER)
        with pytest.raises(TerminalModelError):
            _ = model.propose(a_directive()).proposal
        assert len(model.backend.prompts) == 1


class TestADirective:
    def test_it_cannot_be_edited(self):
        directive = a_directive()
        with pytest.raises(ValidationError):
            directive.index = 4

    def test_it_refuses_a_blank_parent(self):
        with pytest.raises(ValidationError):
            Directive(parent="  ", code="x = 1")

    def test_it_survives_json(self):
        directive = a_directive()
        assert Directive.model_validate_json(directive.model_dump_json()) == directive


class TestMarkersAreConfigurable:
    def test_the_default_pair_is_found(self):
        code = "a = 1\n# CADENCE:BEGIN\nx = 1\n# CADENCE:END\nb = 2\n"
        directive = Directive(parent="p", code=code)
        proposal = (
            a_model("```python\nx = 9\n```", template="region")
            .propose(directive)
            .proposal
        )
        assert "+x = 9" in proposal.patch

    def test_another_pair_can_be_used(self):
        code = "a = 1\n# EVOLVE-START\nx = 1\n# EVOLVE-END\nb = 2\n"
        directive = Directive(parent="p", code=code)
        model = Model(
            backend=Scripted("```python\nx = 9\n```"),
            template="region",
            markers=("EVOLVE-START", "EVOLVE-END"),
        )
        assert "+x = 9" in model.propose(directive).proposal.patch

    def test_a_program_without_the_configured_pair_is_rewritten_whole(self):
        code = "x = 1\n"
        directive = Directive(parent="p", code=code)
        model = Model(
            backend=Scripted("```python\nx = 9\n```"),
            template="region",
            markers=("EVOLVE-START", "EVOLVE-END"),
        )
        assert "+x = 9" in model.propose(directive).proposal.patch


class TestTheModelIsToldWhereItStands:
    """Without this the loop is selection without learning: a model handed a
    program and "try a different strategy entirely", with no idea what the
    program in front of it scored, what better would mean, or what its
    siblings managed. It cannot climb a hill it cannot see."""

    def _prompt(self, standing=None, goals=None, problem=None):
        model = Model(backend=Scripted(ANSWER), template="improve", goals=goals)
        directive = Directive(
            parent="abc123", code="def solve(): return []", standing=standing
        )
        return model.prepare(directive, "k", problem=problem).prompt

    def test_the_parents_score_is_in_the_prompt(self):
        assert "ms = 0.698" in self._prompt(standing={"ms": 0.698})

    def test_it_says_which_way_is_better(self):
        """A number alone does not say what improving it means, and that is
        the one thing the model cannot work out from the code."""
        prompt = self._prompt(standing={"ms": 0.698}, goals={"ms": "minimize"})
        assert "lower is better" in prompt

    def test_maximizing_reads_the_other_way(self):
        prompt = self._prompt(standing={"value": 45.0}, goals={"value": "maximize"})
        assert "higher is better" in prompt

    def test_every_metric_is_reported(self):
        prompt = self._prompt(
            standing={"value": 45.0, "weight": 19.0},
            goals={"value": "maximize", "weight": "minimize"},
        )
        assert "value = 45" in prompt
        assert "weight = 19" in prompt

    def test_a_metric_with_no_declared_direction_still_appears(self):
        """The manifest and the verdict can disagree -- a verifier may print
        more than it was asked for. Printing the number without a direction
        beats dropping it."""
        assert "extra = 3" in self._prompt(standing={"extra": 3.0}, goals={})

    def test_an_unscored_seed_says_so_rather_than_claiming_a_zero(self):
        prompt = self._prompt(standing=None)
        assert "Nobody has scored" in prompt
        assert "= 0" not in prompt

    def test_two_parents_with_different_scores_ask_different_questions(self):
        assert self._prompt(standing={"ms": 1.0}) != self._prompt(standing={"ms": 2.0})


class TestARejectedReplyIsExplained:
    """Three identical asks buy three chances at the same mistake. The retry
    is only worth its call if it is a better question than the first."""

    def _prompt(self, problem=None):
        model = Model(backend=Scripted(ANSWER), template="improve")
        return model.prepare(a_directive(), "k", problem=problem).prompt

    def test_the_reason_reaches_the_model(self):
        assert "no closed ```python block" in self._prompt(
            problem="the response has no closed ```python block"
        )

    def test_a_first_attempt_carries_no_complaint(self):
        prompt = self._prompt()
        assert "could not be used" not in prompt
        assert "\n\n\n" not in prompt

    def test_it_is_part_of_the_recipe_so_replay_reproduces_it(self):
        model = Model(backend=Scripted(ANSWER), template="improve")
        request = model.prepare(a_directive(), "k", problem="the block was empty")
        assert render(request.recipe) == request.prompt

    def test_the_retry_is_not_the_same_question(self):
        assert self._prompt(problem="the block was empty") != self._prompt()


class TestGuidanceReachesTheModel:
    def test_it_appears_in_the_prompt(self):
        model = Model(
            backend=Scripted(ANSWER),
            template="improve",
            guidance="Do not edit items.py.",
        )
        suggestion = model.propose(a_directive())
        assert "Do not edit items.py." in suggestion.proposal.prompt

    def test_it_is_part_of_the_recipe_so_replay_reproduces_it(self):
        model = Model(
            backend=Scripted(ANSWER),
            template="improve",
            guidance="Do not edit items.py.",
        )
        proposal = model.propose(a_directive()).proposal
        assert render(proposal.recipe) == proposal.prompt

    def test_no_guidance_leaves_no_gap_in_the_prompt(self):
        model = Model(backend=Scripted(ANSWER), template="improve")
        prompt = model.propose(a_directive()).proposal.prompt
        assert "What matters here" not in prompt
        assert "\n\n\n" not in prompt
