import pytest
from pydantic import ValidationError

from cadence.control.backends import Scripted
from cadence.control.model import Model, parse_patch, render
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


def a_directive(hint="try a greedy pass"):
    return Directive(parent="abc123", code="def solve(): return []", hint=hint)


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

    def test_the_prompt_carries_the_hint(self):
        proposal = a_model(ANSWER).propose(a_directive(hint="use a heap")).proposal
        assert "use a heap" in proposal.prompt

    def test_a_different_hint_gives_a_different_prompt(self):
        first = a_model(ANSWER).propose(a_directive(hint="one")).proposal
        second = a_model(ANSWER).propose(a_directive(hint="two")).proposal
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
        directive = Directive(parent="p", code=marked, hint="try something")
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
            directive.hint = "something else"

    def test_it_refuses_a_blank_hint(self):
        with pytest.raises(ValidationError):
            Directive(parent="abc", code="x = 1", hint="  ")

    def test_it_survives_json(self):
        directive = a_directive()
        assert Directive.model_validate_json(directive.model_dump_json()) == directive


class TestMarkersAreConfigurable:
    def test_the_default_pair_is_found(self):
        code = "a = 1\n# CADENCE:BEGIN\nx = 1\n# CADENCE:END\nb = 2\n"
        directive = Directive(parent="p", code=code, hint="try")
        proposal = (
            a_model("```python\nx = 9\n```", template="region")
            .propose(directive)
            .proposal
        )
        assert "+x = 9" in proposal.patch

    def test_another_pair_can_be_used(self):
        code = "a = 1\n# EVOLVE-START\nx = 1\n# EVOLVE-END\nb = 2\n"
        directive = Directive(parent="p", code=code, hint="try")
        model = Model(
            backend=Scripted("```python\nx = 9\n```"),
            template="region",
            markers=("EVOLVE-START", "EVOLVE-END"),
        )
        assert "+x = 9" in model.propose(directive).proposal.patch

    def test_a_program_without_the_configured_pair_is_rewritten_whole(self):
        code = "x = 1\n"
        directive = Directive(parent="p", code=code, hint="try")
        model = Model(
            backend=Scripted("```python\nx = 9\n```"),
            template="region",
            markers=("EVOLVE-START", "EVOLVE-END"),
        )
        assert "+x = 9" in model.propose(directive).proposal.patch


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
