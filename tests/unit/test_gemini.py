import os

import pytest

from cadence.backends import Backend, Gemini
from cadence.exceptions import RetryableModelError, TerminalModelError

KEYED = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


class Failure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"status {code}")


class TestTheBackend:
    def test_it_satisfies_the_protocol(self):
        assert isinstance(Gemini(api_key="x"), Backend)

    def test_it_is_named(self):
        assert Gemini(api_key="x").name == "gemini"

    def test_it_is_registered_under_a_name(self):
        from cadence.registry import BACKENDS

        assert BACKENDS["gemini"] is Gemini

    def test_it_does_not_build_a_client_until_asked(self):
        assert Gemini(api_key="x")._client is None


class TestWithoutAKey:
    def test_it_says_which_variable_to_set(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(TerminalModelError, match="GEMINI_API_KEY"):
            Gemini().call("hello")

    def test_a_missing_key_is_terminal_not_retryable(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(TerminalModelError):
            Gemini().call("hello")

    def test_the_environment_supplies_one(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "from-the-env")
        assert Gemini()._key == "from-the-env"

    def test_an_explicit_key_wins(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "from-the-env")
        assert Gemini(api_key="explicit")._key == "explicit"


class TestErrorsAreClassifiedByTheError:
    @pytest.mark.parametrize("code", [429, 500, 503, 504])
    def test_rate_limits_and_server_errors_are_retryable(self, code):
        from cadence.backends import _from_api

        assert isinstance(_from_api(Failure(code)), RetryableModelError)

    @pytest.mark.parametrize("code", [400, 401, 403, 404])
    def test_a_bad_key_or_model_is_terminal(self, code):
        from cadence.backends import _from_api

        assert isinstance(_from_api(Failure(code)), TerminalModelError)

    def test_an_unknown_status_is_terminal(self):
        from cadence.backends import _from_api

        assert isinstance(_from_api(Failure(None)), TerminalModelError)


@pytest.mark.skipif(not KEYED, reason="needs GEMINI_API_KEY")
class TestAgainstTheRealApi:
    def test_it_answers(self):
        assert Gemini().call("Reply with one word.").text.strip()

    def test_it_reports_what_the_call_cost(self):
        completion = Gemini().call("Reply with one word.")
        assert completion.tokens_in > 0
        assert completion.tokens_out > 0

    def test_an_unknown_model_is_terminal(self):
        with pytest.raises(TerminalModelError):
            Gemini(model="gemini-does-not-exist").call("hello")
