import pytest

from cadence.backends import (
    PROVIDERS,
    Backend,
    Gemini,
    Ollama,
    Reliable,
    Scripted,
    served,
)
from cadence.registry import BACKENDS
from cadence.exceptions import RetryableModelError, TerminalModelError
from cadence.http import RETRYABLE, Http


class Recorded:
    """Stands in for the network. Answers, or raises what a server would."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.sent = []

    def post(self, url, payload, headers=None):
        self.sent.append((url, payload, headers or {}))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def an_answer(**fields):
    from cadence.http import Answer

    answer = Answer(fields)
    answer.latency_ms = 12.0
    return answer


class TestOneClientForEveryProvider:
    def test_every_provider_is_a_backend(self):
        for name in PROVIDERS:
            assert isinstance(BACKENDS[name](), Backend)

    def test_every_provider_is_wrapped_the_same_way(self):
        for name in PROVIDERS:
            assert isinstance(BACKENDS[name](), Reliable)

    def test_a_provider_is_named(self):
        assert served("ollama").name == "ollama"

    def test_an_unknown_provider_lists_the_known_ones(self):
        with pytest.raises(TerminalModelError, match="gemini, ollama"):
            served("nope")

    def test_the_transport_is_injected(self):
        http = Recorded(an_answer(response="hi", model="m"))
        assert Ollama(http=http).call("a prompt").text == "hi"

    def test_an_sdk_backend_gets_the_same_retries_and_audit(self):
        """Anything satisfying Backend is wrapped identically. No HTTP involved."""
        seen, tries = [], []

        class SdkBackend:
            name = "sdk"

            def call(self, prompt):
                tries.append(1)
                if len(tries) < 2:
                    raise RetryableModelError("busy")
                return Scripted("done").call(prompt)

        backend = Reliable(SdkBackend(), attempts=3, backoff=0, audit=seen.append)
        assert backend.call("p").text == "done"
        assert len(tries) == 2
        assert [entry["attempt"] for entry in seen] == [1, 2]
        assert backend.name == "sdk"

    def test_the_prompt_reaches_the_provider(self):
        http = Recorded(an_answer(response="hi", model="m"))
        Ollama(http=http).call("a prompt")
        assert http.sent[0][1]["prompt"] == "a prompt"

    def test_gemini_sends_its_key_as_a_header(self):
        http = Recorded(
            an_answer(candidates=[{"content": {"parts": [{"text": "hi"}]}}])
        )
        Gemini(http=http, api_key="secret").call("p")
        assert http.sent[0][2]["x-goog-api-key"] == "secret"

    def test_a_blocked_answer_with_no_candidates_is_empty_not_a_crash(self):
        http = Recorded(an_answer(candidates=[]))
        assert Gemini(http=http, api_key="x").call("p").text == ""

    def test_gemini_without_a_key_is_terminal(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(TerminalModelError, match="GEMINI_API_KEY"):
            Gemini(http=Recorded()).call("p")


class TestReadingWhatCameBack:
    def test_ollama_reports_what_the_call_cost(self):
        http = Recorded(
            an_answer(response="hi", model="m", prompt_eval_count=7, eval_count=3)
        )
        completion = Ollama(http=http).call("p")
        assert (completion.tokens_in, completion.tokens_out) == (7, 3)

    def test_gemini_reports_what_the_call_cost(self):
        http = Recorded(
            an_answer(
                candidates=[{"content": {"parts": [{"text": "hi"}]}}],
                usageMetadata={"promptTokenCount": 7, "candidatesTokenCount": 3},
            )
        )
        completion = Gemini(http=http, api_key="x").call("p")
        assert (completion.text, completion.tokens_in, completion.tokens_out) == (
            "hi",
            7,
            3,
        )

    def test_the_latency_comes_from_the_transport(self):
        http = Recorded(an_answer(response="hi", model="m"))
        assert Ollama(http=http).call("p").latency_ms == 12.0


class TestWhatIsWorthRetrying:
    @pytest.mark.parametrize("status", sorted(RETRYABLE))
    def test_these_are_retryable(self, status):
        from cadence.http import _classify

        assert isinstance(_classify(status, ""), RetryableModelError)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_these_are_terminal(self, status):
        from cadence.http import _classify

        assert isinstance(_classify(status, ""), TerminalModelError)

    def test_it_retries_a_retryable_error(self):
        http = Recorded(RetryableModelError("429"), an_answer(response="hi", model="m"))
        assert Ollama(http=http, attempts=2, backoff=0).call("p").text == "hi"

    def test_an_unreachable_host_is_retryable(self):
        with pytest.raises(RetryableModelError, match="did not answer"):
            Http(timeout=1).post("http://127.0.0.1:1/x", {})

    def test_it_gives_up_after_the_attempt_budget(self):
        http = Recorded(*[RetryableModelError("429")] * 3)
        with pytest.raises(RetryableModelError):
            Ollama(http=http, attempts=3, backoff=0).call("p")
        assert len(http.sent) == 3

    def test_a_terminal_error_is_not_retried(self):
        http = Recorded(TerminalModelError("401"))
        with pytest.raises(TerminalModelError):
            Ollama(http=http, attempts=3, backoff=0).call("p")
        assert len(http.sent) == 1


class TestEveryCallIsAudited:
    def test_a_success_is_recorded(self):
        seen = []
        http = Recorded(an_answer(response="hi", model="m"))
        Ollama(http=http, audit=seen.append).call("p")
        assert seen[0]["backend"] == "ollama" and seen[0]["error"] is None

    def test_a_failure_is_recorded_with_its_error(self):
        seen = []
        http = Recorded(TerminalModelError("401"))
        with pytest.raises(TerminalModelError):
            Ollama(http=http, audit=seen.append).call("p")
        assert "TerminalModelError" in seen[0]["error"]

    def test_every_attempt_is_recorded(self):
        seen = []
        http = Recorded(*[RetryableModelError("429")] * 3)
        with pytest.raises(RetryableModelError):
            Ollama(http=http, attempts=3, backoff=0, audit=seen.append).call("p")
        assert [entry["attempt"] for entry in seen] == [1, 2, 3]
