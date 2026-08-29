import socket
import time

import pytest
from pydantic import ValidationError

from cadence.control.backends import Reliable, Scripted, chat_backend, known
from cadence.control.backends.http import (
    RETRYABLE,
    Http,
    HttpResponse,
    _by_turns,
    error_for,
)
from cadence.control.backends.settings import Price, settings_for
from cadence.control.registry import BACKENDS
from cadence.core.dto import Request
from cadence.core.ports import Backend
from cadence.errors import (
    EmptyReply,
    MissingKey,
    RetryableModelError,
    TerminalModelError,
)


def Ollama(**options):
    return chat_backend("ollama", **options)


def Gemini(**options):
    return chat_backend("gemini", **options)


def OpenAI(**options):
    return chat_backend("openai", **options)


class Recorder:
    """An audit that keeps what it was told."""

    def __init__(self):
        self.entries = []

    def succeeded(self, backend, attempt):
        self.entries.append({"backend": backend, "attempt": attempt, "error": None})

    def failed(self, backend, attempt, error):
        self.entries.append(
            {
                "backend": backend,
                "attempt": attempt,
                "error": f"{type(error).__name__}: {error}",
            }
        )


class Recorded:
    """Stands in for the network."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.sent = []

    def post(self, url, request, headers=None):
        self.sent.append((url, request, headers or {}))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def asking(prompt: str = "a prompt", key: str = "run/0") -> Request:
    """What a backend is handed now: the request, not just its text."""
    return Request(
        key=key, prompt=prompt, digest="d" * 16, recipe={"template": "improve"}
    )


def spoke(text="hi", tokens_in=7, tokens_out=3, model="m"):
    return HttpResponse(
        body={
            "model": model,
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
        },
        latency_ms=12.0,
    )


@pytest.fixture(params=["scripted", "reliable_over_http"])
def backend(request):
    """Both kinds of backend: one with the answers written down, one that
    speaks to a provider."""
    if request.param == "scripted":
        return Scripted("an answer", "another answer")
    return Ollama(http=Recorded(spoke("an answer"), spoke("another answer")))


class TestAnyBackend:
    """What every backend must do. A backend added to the fixture above
    inherits all of it, and cannot satisfy less than the others."""

    def test_it_satisfies_the_port(self, backend):
        assert isinstance(backend, Backend)

    def test_it_answers_with_a_completion(self, backend):
        assert backend.call(asking("a prompt")).text == "an answer"

    def test_it_reports_which_model_answered(self, backend):
        assert backend.call(asking("a prompt")).model

    def test_it_names_itself_the_same_way_every_time(self, backend):
        assert backend.name == backend.name

    def test_asking_twice_gives_two_answers(self, backend):
        assert backend.call(asking("one")).text != backend.call(asking("two")).text

    def test_the_cost_of_a_call_is_reported(self, backend):
        cost = backend.call(asking("a prompt")).cost
        assert set(cost) == {"tokens_in", "tokens_out", "latency_ms", "cost_usd"}


class TestWhatACallCostInMoney:
    """Tokens are not comparable between two models, so a run against a cheap
    one and a run against an expensive one cannot be told apart by them.
    Money is the only unit that survives the comparison -- and cadence ships
    almost none of it, because a price is a fact about someone else's
    catalogue on the day it was written."""

    def test_a_local_model_is_free_rather_than_unpriced(self):
        """The one price that cannot go stale: nothing bills for a model
        running on your own machine."""
        assert Ollama(http=Recorded(spoke())).call(asking("hi")).cost_usd == 0.0

    def test_a_provider_nobody_priced_reports_no_cost(self):
        """None, not zero. The call cost something; cadence was not told
        what, and inventing a zero would be a lie with a decimal point."""
        assert (
            Gemini(key="x", http=Recorded(spoke())).call(asking("hi")).cost_usd is None
        )

    def test_a_declared_price_is_applied_to_the_tokens(self):
        priced = Gemini(
            key="x",
            prices={"m": {"in": 2.0, "out": 10.0}},
            http=Recorded(spoke(tokens_in=1_000_000, tokens_out=1_000_000)),
        )
        assert priced.call(asking("hi")).cost_usd == 12.0

    def test_it_prices_the_model_that_answered_not_the_one_asked_for(self):
        """A provider that served something else billed for what it served."""
        priced = Gemini(
            key="x",
            model="asked-for",
            prices={"served": {"in": 1.0, "out": 1.0}},
            http=Recorded(spoke(model="served", tokens_in=1_000_000, tokens_out=0)),
        )
        assert priced.call(asking("hi")).cost_usd == 1.0

    def test_a_price_for_one_model_does_not_price_another(self):
        priced = Gemini(
            key="x",
            prices={"other": {"in": 1.0, "out": 1.0}},
            http=Recorded(spoke(model="m")),
        )
        assert priced.call(asking("hi")).cost_usd is None

    def test_a_price_is_quoted_per_million_tokens(self):
        """Because that is how every provider publishes one, so a number
        copied off a pricing page is copied unchanged."""
        price = Price(**{"in": 3.0, "out": 0.0})
        assert price.of(500_000, 0) == 1.5

    def test_a_wildcard_prices_whatever_was_named(self):
        settings = settings_for("ollama")
        assert settings.price_of("a model nobody has heard of") is not None

    def test_a_negative_price_is_refused(self):
        with pytest.raises(ValidationError):
            Price(**{"in": -1.0, "out": 0.0})


class TestPayingOnceForOneCall:
    """Reliable retries a timeout, and a timeout is exactly when the provider
    may have answered a request we never saw. The key names the call so the
    second attempt is recognised as the same one."""

    def _sent(self, provider, **options):
        http = Recorded(spoke())
        provider(http=http, **options).call(asking(key="h1/0#1"))
        return http.sent[0][2]

    def test_the_key_goes_on_the_wire(self):
        headers = self._sent(OpenAI, key="x", model="gpt-x")
        assert headers["Idempotency-Key"] == "h1/0#1"

    def test_a_provider_without_one_sends_nothing_extra(self):
        """ollama declares no header, so there is nothing to claim."""
        assert "Idempotency-Key" not in self._sent(Ollama)

    def test_a_retry_of_the_same_call_sends_the_same_key(self):
        """Two attempts at one call, so the provider can tell they are one."""
        http = Recorded(spoke(), spoke())
        backend = OpenAI(key="x", model="gpt-x", http=http)
        backend.call(asking(key="h1/0"))
        backend.call(asking(key="h1/0"))
        assert [sent[2]["Idempotency-Key"] for sent in http.sent] == ["h1/0", "h1/0"]

    def test_a_different_attempt_is_a_different_key(self):
        """A retry after an unusable reply is a new question, so it is a new
        call and must not be deduped against the last one."""
        http = Recorded(spoke(), spoke())
        backend = OpenAI(key="x", model="gpt-x", http=http)
        backend.call(asking(key="h1/0"))
        backend.call(asking(key="h1/0#1"))
        assert [sent[2]["Idempotency-Key"] for sent in http.sent] == ["h1/0", "h1/0#1"]


class TestConnectingHasItsOwnBudget:
    """A model can think for minutes, so the read timeout is long. Connecting
    should not get to use it."""

    #: TEST-NET-1. Nothing answers here.
    NOWHERE = "http://192.0.2.1:9/v1/chat/completions"

    def test_they_are_two_numbers(self):
        http = Http(timeout=300.0, connect_timeout=2.0)
        assert (http.timeout, http.connect_timeout) == (300.0, 2.0)

    def test_a_host_that_never_answers_gives_up_quickly(self):
        started = time.monotonic()
        with pytest.raises(RetryableModelError):
            Http(timeout=300.0, connect_timeout=1.0).post(self.NOWHERE, {"a": 1})
        assert time.monotonic() - started < 30.0

    def test_it_is_worth_retrying(self):
        with pytest.raises(RetryableModelError):
            Http(timeout=300.0, connect_timeout=1.0).post(self.NOWHERE, {"a": 1})


class TestAddressesAreTriedInTurns:
    """A resolver lists one family first. If that family is a black hole,
    trying them in order spends every attempt on it."""

    def _info(self, family, host):
        return (family, socket.SOCK_STREAM, 6, "", (host, 443))

    def test_the_second_address_is_from_the_other_family(self):
        six = [self._info(socket.AF_INET6, f"::{n}") for n in range(1, 4)]
        four = [self._info(socket.AF_INET, f"10.0.0.{n}") for n in range(1, 4)]
        taken = _by_turns(six + four)
        assert [info[0] for info in taken[:2]] == [socket.AF_INET6, socket.AF_INET]

    def test_no_address_is_dropped(self):
        six = [self._info(socket.AF_INET6, f"::{n}") for n in range(1, 4)]
        four = [self._info(socket.AF_INET, "10.0.0.1")]
        assert len(_by_turns(six + four)) == 4

    def test_the_order_within_a_family_is_kept(self):
        six = [self._info(socket.AF_INET6, f"::{n}") for n in range(1, 4)]
        taken = [i for i in _by_turns(six) if i[0] == socket.AF_INET6]
        assert [info[4][0] for info in taken] == ["::1", "::2", "::3"]

    def test_one_family_alone_is_left_as_it_is(self):
        four = [self._info(socket.AF_INET, f"10.0.0.{n}") for n in range(1, 4)]
        assert _by_turns(four) == four


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
        from cadence.errors import UnknownProvider

        with pytest.raises(UnknownProvider, match="no default model"):
            settings_for("openai")

    def test_naming_one_is_enough(self):
        assert settings_for("openai", model="gpt-4.1").model == "gpt-4.1"

    def test_an_unknown_one_lists_the_known_ones(self):
        from cadence.errors import UnknownProvider

        with pytest.raises(UnknownProvider, match="gemini"):
            chat_backend("nope")

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
        Gemini(http=http, key="secret").call(asking("p"))
        assert http.sent[0][2]["Authorization"] == "Bearer secret"

    def test_a_local_model_sends_no_authorization(self):
        http = Recorded(spoke())
        Ollama(http=http).call(asking("p"))
        assert "Authorization" not in http.sent[0][2]


class TestTheDialect:
    def test_the_prompt_goes_in_a_message(self):
        http = Recorded(spoke())
        Ollama(http=http).call(asking("a prompt"))
        assert http.sent[0][1]["messages"] == [{"role": "user", "content": "a prompt"}]

    def test_it_posts_to_chat_completions(self):
        http = Recorded(spoke())
        Ollama(http=http).call(asking("p"))
        assert http.sent[0][0].endswith("/chat/completions")

    def test_the_answer_is_read(self):
        assert Ollama(http=Recorded(spoke("hello"))).call(asking("p")).text == "hello"

    def test_the_cost_is_read(self):
        completion = Ollama(http=Recorded(spoke(tokens_in=11, tokens_out=5))).call(
            asking("p")
        )
        assert (completion.tokens_in, completion.tokens_out) == (11, 5)

    def test_a_reply_with_no_choices_costs_a_trial_not_the_run(self):
        """A content filter or a truncation. Not an empty completion, which
        would be blamed on the model and retried as unparseable prose."""
        answer = HttpResponse(body={"choices": []}, latency_ms=1.0)
        with pytest.raises(EmptyReply, match="ollama returned a reply"):
            Ollama(http=Recorded(answer)).call(asking("p"))

    def test_a_body_that_is_not_a_reply_at_all_blames_the_provider(self):
        answer = HttpResponse(body={"error": {"message": "quota"}}, latency_ms=1.0)
        with pytest.raises(TerminalModelError, match="could not read"):
            Ollama(http=Recorded(answer)).call(asking("p"))

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"choices": []}, id="no choices"),
            pytest.param({"choices": [{}]}, id="a choice with no message"),
            pytest.param({"choices": [{"message": None}]}, id="a null message"),
            pytest.param(
                {"choices": [{"message": {"content": None}}]}, id="null content"
            ),
        ],
    )
    def test_every_spelling_of_saying_nothing_costs_a_trial(self, body):
        """A provider has four ways to say the same thing, and null content is
        the common one -- it is what a refusal and a tool call both look
        like. Treating any of them as a body we cannot read would end the run
        on a reply that is perfectly well formed."""
        answer = HttpResponse(body=body, latency_ms=1.0)
        with pytest.raises(EmptyReply):
            Ollama(http=Recorded(answer)).call(asking("p"))

    def test_a_reply_with_no_usage_is_read_as_costing_nothing_known(self):
        """Gateways send `"usage": null`. It is not a reason to lose the run."""
        answer = HttpResponse(
            body={"choices": [{"message": {"content": "hi"}}], "usage": None},
            latency_ms=1.0,
        )
        completion = Ollama(http=Recorded(answer)).call(asking("p"))
        assert (completion.text, completion.tokens_in) == ("hi", 0)

    def test_the_latency_comes_from_the_transport(self):
        assert Ollama(http=Recorded(spoke())).call(asking("p")).latency_ms == 12.0


class TestWhatIsWorthRetrying:
    @pytest.mark.parametrize("status", sorted(RETRYABLE))
    def test_these_are_retryable(self, status):
        assert isinstance(error_for(status, ""), RetryableModelError)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_these_are_terminal(self, status):
        assert isinstance(error_for(status, ""), TerminalModelError)

    def test_a_retryable_error_is_retried(self):
        http = Recorded(RetryableModelError("429"), spoke("hi"))
        assert Ollama(http=http, attempts=2, backoff=0).call(asking("p")).text == "hi"

    def test_it_gives_up_after_the_attempt_budget(self):
        http = Recorded(*[RetryableModelError("429")] * 3)
        with pytest.raises(RetryableModelError):
            Ollama(http=http, attempts=3, backoff=0).call(asking("p"))
        assert len(http.sent) == 3

    def test_a_terminal_error_is_not_retried(self):
        http = Recorded(TerminalModelError("401"))
        with pytest.raises(TerminalModelError):
            Ollama(http=http, attempts=3, backoff=0).call(asking("p"))
        assert len(http.sent) == 1

    def test_an_unreachable_host_is_retryable(self):
        with pytest.raises(RetryableModelError, match="did not answer"):
            Http(timeout=1).post("http://127.0.0.1:1/x", {})


class TestAnythingCanBeMadeReliable:
    def test_a_backend_with_no_http_gets_the_same_treatment(self):
        seen, tries = Recorder(), []

        class SdkBackend:
            name = "sdk"

            def call(self, prompt):
                tries.append(1)
                if len(tries) < 2:
                    raise RetryableModelError("busy")
                return Scripted("done").call(prompt)

        backend = Reliable(SdkBackend(), attempts=3, backoff=0, audit=seen)
        assert backend.call(asking("p")).text == "done"
        assert len(tries) == 2
        assert [entry["attempt"] for entry in seen.entries] == [1, 2]


class TestEveryCallIsAudited:
    def test_a_success_is_recorded(self):
        seen = Recorder()
        Ollama(http=Recorded(spoke()), audit=seen).call(asking("p"))
        assert seen.entries[0]["backend"] == "ollama"
        assert seen.entries[0]["error"] is None

    def test_a_failure_is_recorded_with_its_error(self):
        seen = Recorder()
        with pytest.raises(TerminalModelError):
            Ollama(http=Recorded(TerminalModelError("401")), audit=seen).call(
                asking("p")
            )
        assert "TerminalModelError" in seen.entries[0]["error"]

    def test_a_reply_that_said_nothing_is_still_a_call_someone_paid_for(self):
        seen = Recorder()
        answer = HttpResponse(body={"choices": []}, latency_ms=1.0)
        with pytest.raises(EmptyReply):
            Ollama(http=Recorded(answer), audit=seen).call(asking("p"))
        assert len(seen.entries) == 1
        assert "EmptyReply" in seen.entries[0]["error"]

    def test_every_attempt_is_recorded(self):
        seen = Recorder()
        http = Recorded(*[RetryableModelError("429")] * 3)
        with pytest.raises(RetryableModelError):
            Ollama(http=http, attempts=3, backoff=0, audit=seen).call(asking("p"))
        assert [entry["attempt"] for entry in seen.entries] == [1, 2, 3]
