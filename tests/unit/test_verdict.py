import pytest
from pydantic import TypeAdapter, ValidationError

from cadence.exceptions import (
    CadenceError,
    ModelError,
    RetryableModelError,
    TerminalModelError,
)
from cadence.verdict import FAILURES, Failed, Outcome, Proposal, Scored, Verdict

FP = "a1b2c3"
FAILURE_IDS = [o.value for o in FAILURES]
parse = TypeAdapter(Verdict).validate_python


class TestScored:
    def test_carries_its_metrics(self):
        v = Scored(fingerprint=FP, metrics={"cost": 12.5, "wall_time": 0.4})
        assert v.is_scored
        assert v.metrics == {"cost": 12.5, "wall_time": 0.4}

    def test_metrics_are_open_ended(self):
        v = Scored(fingerprint=FP, metrics={"sharpe": 1.9, "max_drawdown": 0.2})
        assert set(v.metrics) == {"sharpe", "max_drawdown"}

    def test_needs_at_least_one_metric(self):
        with pytest.raises(ValidationError):
            Scored(fingerprint=FP, metrics={})

    def test_cannot_be_given_a_reason(self):
        with pytest.raises(ValidationError):
            Scored(fingerprint=FP, metrics={"cost": 1.0}, reason="but also this")

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_a_non_finite_metric_is_refused(self, bad):
        with pytest.raises(ValidationError):
            Scored(fingerprint=FP, metrics={"cost": bad})

    def test_a_boolean_is_not_a_measurement(self):
        with pytest.raises(ValidationError):
            Scored(fingerprint=FP, metrics={"feasible": True})

    def test_metrics_cannot_be_mutated_afterwards(self):
        v = Scored(fingerprint=FP, metrics={"cost": 1.0})
        with pytest.raises(TypeError):
            v.metrics["cost"] = 2.0

    def test_is_frozen(self):
        v = Scored(fingerprint=FP, metrics={"cost": 1.0})
        with pytest.raises(ValidationError):
            v.fingerprint = "other"


class TestFailed:
    @pytest.mark.parametrize("outcome", FAILURES, ids=FAILURE_IDS)
    def test_must_say_why(self, outcome):
        with pytest.raises(ValidationError):
            Failed(outcome=outcome, fingerprint=FP)

    @pytest.mark.parametrize("outcome", FAILURES, ids=FAILURE_IDS)
    def test_cannot_carry_metrics(self, outcome):
        with pytest.raises(ValidationError):
            Failed(
                outcome=outcome,
                fingerprint=FP,
                reason="boom",
                metrics={"cost": 1.0},
            )

    @pytest.mark.parametrize("outcome", FAILURES, ids=FAILURE_IDS)
    def test_is_not_scored(self, outcome):
        assert not Failed(outcome=outcome, fingerprint=FP, reason="boom").is_scored

    def test_cannot_claim_to_be_scored(self):
        with pytest.raises(ValidationError):
            Failed(outcome=Outcome.SCORED, fingerprint=FP, reason="boom")

    def test_a_blank_reason_is_no_reason(self):
        with pytest.raises(ValidationError):
            Failed(outcome=Outcome.CRASHED, fingerprint=FP, reason="   ")


class TestOutcomesAreDistinguishable:
    def test_every_failure_mode_has_its_own_outcome(self):
        assert len(set(Outcome)) == 6

    def test_a_crash_is_not_an_invalid_result(self):
        crashed = Failed(outcome=Outcome.CRASHED, fingerprint=FP, reason="ZeroDivision")
        invalid = Failed(outcome=Outcome.INVALID, fingerprint=FP, reason="revisits")
        assert crashed.outcome is not invalid.outcome

    def test_only_a_broken_verifier_escalates(self):
        assert Failed(
            outcome=Outcome.VERIFIER_ERROR, fingerprint=FP, reason="KeyError"
        ).escalates
        assert not Scored(fingerprint=FP, metrics={"cost": 1.0}).escalates
        for outcome in FAILURES:
            if outcome is Outcome.VERIFIER_ERROR:
                continue
            assert not Failed(outcome=outcome, fingerprint=FP, reason="boom").escalates


class TestParsingFromStorage:
    def test_a_scored_row_becomes_a_scored_verdict(self):
        v = parse({"outcome": "scored", "fingerprint": FP, "metrics": {"cost": 1.0}})
        assert isinstance(v, Scored)

    def test_a_failed_row_becomes_a_failed_verdict(self):
        v = parse({"outcome": "crashed", "fingerprint": FP, "reason": "boom"})
        assert isinstance(v, Failed)

    def test_a_scored_row_without_metrics_is_refused(self):
        with pytest.raises(ValidationError):
            parse({"outcome": "scored", "fingerprint": FP})

    def test_an_unknown_outcome_is_refused(self):
        with pytest.raises(ValidationError):
            parse({"outcome": "vibes", "fingerprint": FP, "reason": "boom"})


class TestFingerprint:
    @pytest.mark.parametrize("bad", ["", "   "])
    def test_is_required(self, bad):
        with pytest.raises(ValidationError):
            Scored(fingerprint=bad, metrics={"cost": 1.0})


class TestProposal:
    def make(self, **over):
        kwargs = {
            "patch": ("### START_BLOCK\npass\n### END_BLOCK",),
            "prompt": "improve this",
            "recipe": {"template": "default", "template_hash": "deadbeef"},
            "raw_response": "here you go",
        }
        kwargs.update(over)
        return Proposal(**kwargs)

    def test_carries_the_evidence_not_just_the_patch(self):
        p = self.make()
        assert p.prompt and p.recipe and p.raw_response

    def test_a_recipe_is_required(self):
        with pytest.raises(ValidationError):
            self.make(recipe={})

    def test_the_prompt_is_required(self):
        with pytest.raises(ValidationError):
            self.make(prompt="")

    def test_patch_must_be_a_tuple(self):
        with pytest.raises(ValidationError):
            self.make(patch=["one"])

    def test_recipe_cannot_be_mutated_afterwards(self):
        with pytest.raises(TypeError):
            self.make().recipe["template"] = "other"

    def test_an_empty_patch_is_allowed(self):
        assert self.make(patch=()).patch == ()


class TestErrorTaxonomy:
    def test_retryable_and_terminal_are_both_model_errors(self):
        assert issubclass(RetryableModelError, ModelError)
        assert issubclass(TerminalModelError, ModelError)

    def test_they_are_not_each_other(self):
        assert not issubclass(TerminalModelError, RetryableModelError)
        assert not issubclass(RetryableModelError, TerminalModelError)

    def test_catching_terminal_does_not_catch_retryable(self):
        with pytest.raises(RetryableModelError):
            try:
                raise RetryableModelError("429")
            except TerminalModelError:
                pytest.fail("a retryable error was swallowed as terminal")

    def test_everything_descends_from_one_base(self):
        for err in (ModelError, RetryableModelError, TerminalModelError):
            assert issubclass(err, CadenceError)


class TestWritingToStorage:
    def test_a_scored_verdict_survives_json(self):
        verdict = Scored(fingerprint="abc", metrics={"sharpe": 1.4})
        assert TypeAdapter(Verdict).validate_json(verdict.model_dump_json()) == verdict

    def test_a_failed_verdict_survives_json(self):
        verdict = Failed(fingerprint="abc", outcome=Outcome.CRASHED, reason="boom")
        assert TypeAdapter(Verdict).validate_json(verdict.model_dump_json()) == verdict

    def test_a_proposal_survives_json(self):
        proposal = Proposal(
            patch=("--- a", "+++ b"),
            prompt="improve",
            recipe={"k": 1},
            raw_response="raw",
        )
        assert Proposal.model_validate_json(proposal.model_dump_json()) == proposal

    def test_serializing_does_not_warn(self, recwarn):
        Scored(fingerprint="abc", metrics={"sharpe": 1.4}).model_dump()
        assert not [w for w in recwarn if issubclass(w.category, UserWarning)]

    def test_the_mapping_is_still_immutable(self):
        verdict = Scored(fingerprint="abc", metrics={"sharpe": 1.4})
        with pytest.raises(TypeError):
            verdict.metrics["sharpe"] = 9.9
