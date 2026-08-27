import pytest

from cadence.control.backends.served import (
    Backend,
    Gemini,
    Ollama,
    Reliable,
    Scripted,
    served,
)
from cadence.control.backends.settings import MissingKey, known, settings_for
from cadence.control.registry import BACKENDS
from cadence.exceptions import RetryableModelError, TerminalModelError
from cadence.http import RETRYABLE, Answer, Http


class Recorded:
    """Stands in for the network."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.sent = []

    def post(self, url, payload, headers=None):
        self.sent.append((url, payload, headers or {}))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def spoke(text="hi", tokens_in=7, tokens_out=3, model="m"):
    answer = Answer(
        {
            "model": model,
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
        }
    )
    answer.latency_ms = 12.0
    return answer


class TestProvidersAreData:
    def test_more_than_one_is_known(self):
        assert {"ollama", "gemini"} <= set(known())

    def test_each_one_is_a_backend(self):
        for name in known():
            assert isinstance(BACKENDS[name](key="x", model="m"), Backend)

    def test_each_one_is_wrapped_the_same_way(self):
        for name in known():
            assert isinstance(BACKENDS[name](key="x", model="m"), Reliable)

    def test_a_provider_cadence_has_called_ships_a_model(self):
        assert settings_for("gemini").model
        assert settings_for("ollama").model

    def test_one_it_has_not_makes_you_name_your_own(self):
        from cadence.control.backends.settings import UnknownProvider

        with pytest.raises(UnknownProvider, match="no default model"):
            settings_for("openai")

    def test_naming_one_is_enough(self):
        assert settings_for("openai", model="gpt-4.1").model == "gpt-4.1"

    def test_an_unknown_one_lists_the_known_ones(self):
        from cadence.control.backends.settings import UnknownProvider

        with pytest.raises(UnknownProvider, match="gemini"):
            served("nope")

    def test_adding_one_needs_no_python(self):
        """Every provider differs only in settings, so the classes are identical."""
        assert type(Ollama().backend) is type(Gemini(key="x").backend)


class TestSettings:
    def test_defaults_are_applied(self):
        assert settings_for("ollama").attempts == 3

    def test_a_provider_may_override_a_default(self):
        assert settings_for("gemini").timeout == 120.0

    def test_a_caller_may_override_anything(self):
        assert settings_for("gemini", model="other").model == "other"

    def test_the_host_may_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://elsewhere:9")
        assert settings_for("ollama").base_url == "http://elsewhere:9"

    def test_a_trailing_slash_does_not_double_up(self):
        assert settings_for("ollama", base_url="http://x/").url == "http://x"


class TestKeys:
    def test_a_local_model_needs_none(self):
        assert not settings_for("ollama").needs_a_key

    def test_a_hosted_one_does(self):
        assert settings_for("gemini").needs_a_key

    def test_it_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "from-env")
        assert settings_for("gemini").key == "from-env"

    def test_the_second_variable_is_tried_too(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "fallback")
        assert settings_for("gemini").key == "fallback"

    def test_a_missing_one_names_every_variable_that_would_do(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(MissingKey, match="GEMINI_API_KEY or GOOGLE_API_KEY"):
            settings_for("gemini").demand_key()

    def test_a_key_in_a_config_file_is_refused(self, tmp_path, monkeypatch):
        (tmp_path / "providers.local.yml").write_text(
            "providers:\n  gemini:\n    key: sk-oops\n"
        )
        with pytest.raises(MissingKey, match="belong in the environment"):
            settings_for("gemini", root=tmp_path)

    def test_a_config_file_may_still_set_a_model(self, tmp_path):
        (tmp_path / "providers.local.yml").write_text(
            "providers:\n  gemini:\n    model: pinned\n"
        )
        assert settings_for("gemini", root=tmp_path).model == "pinned"

    def test_it_is_sent_as_a_bearer_token(self):
        http = Recorded(spoke())
        Gemini(http=http, key="secret").call("p")
        assert http.sent[0][2]["Authorization"] == "Bearer secret"

    def test_a_local_model_sends_no_authorization(self):
        http = Recorded(spoke())
        Ollama(http=http).call("p")
        assert "Authorization" not in http.sent[0][2]


class TestTheDialect:
    def test_the_prompt_goes_in_a_message(self):
        http = Recorded(spoke())
        Ollama(http=http).call("a prompt")
        assert http.sent[0][1]["messages"] == [{"role": "user", "content": "a prompt"}]

    def test_it_posts_to_chat_completions(self):
        http = Recorded(spoke())
        Ollama(http=http).call("p")
        assert http.sent[0][0].endswith("/chat/completions")

    def test_the_answer_is_read(self):
        assert Ollama(http=Recorded(spoke("hello"))).call("p").text == "hello"

    def test_the_cost_is_read(self):
        completion = Ollama(http=Recorded(spoke(tokens_in=11, tokens_out=5))).call("p")
        assert (completion.tokens_in, completion.tokens_out) == (11, 5)

    def test_an_empty_answer_is_empty_text_not_a_crash(self):
        answer = Answer({"choices": []})
        answer.latency_ms = 1.0
        assert Ollama(http=Recorded(answer)).call("p").text == ""

    def test_the_latency_comes_from_the_transport(self):
        assert Ollama(http=Recorded(spoke())).call("p").latency_ms == 12.0


class TestWhatIsWorthRetrying:
    @pytest.mark.parametrize("status", sorted(RETRYABLE))
    def test_these_are_retryable(self, status):
        from cadence.http import _classify

        assert isinstance(_classify(status, ""), RetryableModelError)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_these_are_terminal(self, status):
        from cadence.http import _classify

        assert isinstance(_classify(status, ""), TerminalModelError)

    def test_a_retryable_error_is_retried(self):
        http = Recorded(RetryableModelError("429"), spoke("hi"))
        assert Ollama(http=http, attempts=2, backoff=0).call("p").text == "hi"

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

    def test_an_unreachable_host_is_retryable(self):
        with pytest.raises(RetryableModelError, match="did not answer"):
            Http(timeout=1).post("http://127.0.0.1:1/x", {})


class TestAnythingCanBeMadeReliable:
    def test_a_backend_with_no_http_gets_the_same_treatment(self):
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


class TestEveryCallIsAudited:
    def test_a_success_is_recorded(self):
        seen = []
        Ollama(http=Recorded(spoke()), audit=seen.append).call("p")
        assert seen[0]["backend"] == "ollama"
        assert seen[0]["error"] is None

    def test_a_failure_is_recorded_with_its_error(self):
        seen = []
        with pytest.raises(TerminalModelError):
            Ollama(http=Recorded(TerminalModelError("401")), audit=seen.append).call(
                "p"
            )
        assert "TerminalModelError" in seen[0]["error"]

    def test_every_attempt_is_recorded(self):
        seen = []
        http = Recorded(*[RetryableModelError("429")] * 3)
        with pytest.raises(RetryableModelError):
            Ollama(http=http, attempts=3, backoff=0, audit=seen.append).call("p")
        assert [entry["attempt"] for entry in seen] == [1, 2, 3]
