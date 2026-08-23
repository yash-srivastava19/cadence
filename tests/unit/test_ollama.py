import os

import pytest

from cadence.backends import Backend, Ollama

LIVE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def reachable() -> bool:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"{LIVE}/api/tags", timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class TestTheBackend:
    def test_it_satisfies_the_protocol(self):
        assert isinstance(Ollama(), Backend)

    def test_it_is_named(self):
        assert Ollama().name == "ollama"

    def test_the_host_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://elsewhere:1234/")
        assert Ollama().host == "http://elsewhere:1234"

    def test_an_explicit_host_wins(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://elsewhere:1234")
        assert Ollama(host="http://here:9").host == "http://here:9"

    def test_it_is_registered_under_a_name(self):
        from cadence.registry import BACKENDS

        assert BACKENDS["ollama"] is Ollama


class TestWhenItCannotBeReached:
    def test_an_unreachable_host_is_retryable(self):
        from cadence.exceptions import RetryableModelError

        with pytest.raises(RetryableModelError, match="did not answer"):
            Ollama(host="http://127.0.0.1:1", seconds=2).call("hello")


@pytest.mark.skipif(not reachable(), reason=f"needs an ollama at {LIVE}")
class TestAgainstARealModel:
    def test_it_answers(self):
        completion = Ollama(seconds=300).call("Reply with one word.")
        assert completion.text.strip()

    def test_it_reports_what_the_call_cost(self):
        completion = Ollama(seconds=300).call("Reply with one word.")
        assert completion.tokens_in > 0
        assert completion.tokens_out > 0
        assert completion.latency_ms > 0

    def test_an_unknown_model_is_terminal(self):
        from cadence.exceptions import TerminalModelError

        with pytest.raises(TerminalModelError):
            Ollama(model="no-such-model:latest", seconds=60).call("hello")
