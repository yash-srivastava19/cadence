import pytest
from pydantic import ValidationError

from cadence.backends import Backend, Completion, Scripted
from cadence.exceptions import RetryableModelError, TerminalModelError
from cadence.signals import ModelCalled
from cadence.verdict import Proposal


class TestScripted:
    def test_it_satisfies_the_protocol(self):
        assert isinstance(Scripted(), Backend)

    def test_it_answers_in_order(self):
        backend = Scripted("first", "second")
        assert backend.call("a").text == "first"
        assert backend.call("b").text == "second"

    def test_it_remembers_what_it_was_asked(self):
        backend = Scripted("first")
        backend.call("the prompt")
        assert backend.prompts == ["the prompt"]

    def test_the_same_script_gives_the_same_answers(self):
        assert Scripted("x").call("p") == Scripted("x").call("p")

    def test_running_out_is_terminal_rather_than_silent(self):
        backend = Scripted()
        with pytest.raises(TerminalModelError, match="ran out"):
            backend.call("a")

    def test_it_counts_what_is_left(self):
        backend = Scripted("a", "b")
        backend.call("p")
        assert backend.remaining == 1


class TestScriptedFailures:
    def test_it_can_raise_a_retryable_error(self):
        backend = Scripted(RetryableModelError("429"))
        with pytest.raises(RetryableModelError):
            backend.call("a")

    def test_it_can_raise_a_terminal_error(self):
        backend = Scripted(TerminalModelError("401"))
        with pytest.raises(TerminalModelError):
            backend.call("a")

    def test_a_failure_can_sit_between_two_successes(self):
        backend = Scripted("first", RetryableModelError("429"), "third")
        assert backend.call("a").text == "first"
        with pytest.raises(RetryableModelError):
            backend.call("b")
        assert backend.call("c").text == "third"

    def test_a_failure_still_consumes_its_turn(self):
        backend = Scripted(RetryableModelError("429"), "second")
        with pytest.raises(RetryableModelError):
            backend.call("a")
        assert backend.remaining == 1


class TestACompletionCanRecordTheCall:
    def test_it_fills_everything_a_model_called_event_needs(self):
        completion = Scripted("some answer here").call("a prompt")
        event = ModelCalled(
            run_id="h1",
            trial_id="h1/0/0",
            backend=Scripted.name,
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            latency_ms=completion.latency_ms,
        )
        assert event.tokens_out == 3

    def test_it_fills_the_raw_response_a_proposal_keeps(self):
        completion = Scripted("--- a\n+++ b").call("a prompt")
        proposal = Proposal(
            patch=("--- a", "+++ b"),
            prompt="a prompt",
            recipe={"template": "improve"},
            raw_response=completion.text,
        )
        assert proposal.raw_response == completion.text

    def test_it_counts_both_directions(self):
        completion = Scripted("one two three").call("four five")
        assert (completion.tokens_in, completion.tokens_out) == (2, 3)

    def test_it_cannot_be_edited(self):
        completion = Scripted("x").call("p")
        with pytest.raises(ValidationError):
            completion.text = "y"

    def test_a_negative_count_is_refused(self):
        with pytest.raises(ValidationError):
            Completion(text="x", model="m", tokens_in=-1, tokens_out=0, latency_ms=0.0)

    def test_it_survives_json(self):
        completion = Scripted("x").call("p")
        assert (
            Completion.model_validate_json(completion.model_dump_json()) == completion
        )
