import pytest
from pydantic import ValidationError

from cadence.core.verdict import Scored
from cadence.observe.signals import (
    Event,
    ModelCalled,
    PatchRejected,
    TrialMeasured,
    TrialStarted,
    cadence,
)


def a_verdict():
    return Scored(fingerprint="abc", metrics={"sharpe": 1.4})


class TestTheCadenceChannel:
    def test_a_run_can_be_followed_end_to_end(self):
        with cadence.recording() as tape:
            TrialStarted(run_id="h1", trial_id="t1").emit()
            ModelCalled(
                run_id="h1",
                trial_id="t1",
                backend="mock",
                tokens_in=1,
                tokens_out=2,
                latency_ms=3.0,
            ).emit()
            TrialMeasured(run_id="h1", trial_id="t1", verdict=a_verdict()).emit()
        assert [type(fact).__name__ for fact in tape] == [
            "TrialStarted",
            "ModelCalled",
            "TrialMeasured",
        ]

    def test_a_subscriber_can_watch_one_kind(self):
        seen = []
        stop = cadence.subscribe(seen.append, to=PatchRejected)
        TrialStarted(run_id="h1", trial_id="t1").emit()
        PatchRejected(run_id="h1", trial_id="t1", reason="no hunks").emit()
        stop()
        assert len(seen) == 1


class TestEventsAreFacts:
    def test_an_event_refuses_a_blank_run(self):
        with pytest.raises(ValidationError):
            TrialStarted(run_id="   ", trial_id="t1")

    def test_a_count_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            ModelCalled(
                run_id="h1",
                trial_id="t1",
                backend="mock",
                tokens_in=-1,
                tokens_out=0,
                latency_ms=1.0,
            )

    def test_every_event_declares_a_run(self):
        for kind in Event.__subclasses__():
            assert "run_id" in kind.model_fields


class TestWritingToStorage:
    def test_an_event_carrying_a_verdict_survives_json(self):
        event = TrialMeasured(run_id="h1", trial_id="t1", verdict=a_verdict())
        assert TrialMeasured.model_validate_json(event.model_dump_json()) == event

    def test_a_verdict_keeps_its_kind_through_the_round_trip(self):
        event = TrialMeasured(run_id="h1", trial_id="t1", verdict=a_verdict())
        parsed = TrialMeasured.model_validate_json(event.model_dump_json())
        assert parsed.verdict.is_scored

    def test_serializing_does_not_warn(self, recwarn):
        TrialMeasured(run_id="h1", trial_id="t1", verdict=a_verdict()).model_dump()
        assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
