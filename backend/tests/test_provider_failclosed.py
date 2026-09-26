"""Fail-closed provider configuration (OctoberTask.md §6, §33).

An OpenAI-compatible role with no base_url must never reach the OpenAI SDK, because the
SDK silently falls through to api.openai.com. These tests pin that the failure is a loud
``<ROLE>_PROVIDER_UNAVAILABLE`` at both the config and the client boundary, and that a
genuine OpenAI role (which legitimately defaults to api.openai.com) still builds.
"""

import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, SecretStr

from app.coevolution.providers import (
    ChatResult,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderError,
    probe,
)
from app.config import Settings


def test_compatible_config_with_empty_base_url_is_refused() -> None:
    with pytest.raises(ProviderError) as error:
        ProviderConfig(
            role_name="RED",
            provider="openai_compatible",
            base_url="",
            api_key="local",
            model="m",
        )
    assert error.value.code == "RED_PROVIDER_UNAVAILABLE"
    assert "api.openai.com" in error.value.message


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_compatible_config_rejects_none_and_whitespace(blank: str | None) -> None:
    with pytest.raises(ProviderError) as error:
        ProviderConfig(
            role_name="BLUE",
            provider="openai_compatible",
            base_url=blank,
            api_key="local",
            model="m",
        )
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"


def test_openai_role_may_default_to_the_hosted_endpoint() -> None:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openai",
        base_url="",
        api_key="sk-real",
        model="gpt-4.1-mini",
    )
    assert config.provider == "openai"


def test_settings_red_defaults_do_not_silently_target_the_hosted_api() -> None:
    settings = Settings(red_provider="openai_compatible", red_base_url="")
    with pytest.raises(ProviderError) as error:
        ProviderConfig.red(settings)
    assert error.value.code == "RED_PROVIDER_UNAVAILABLE"


def test_settings_blue_compatible_without_url_is_refused() -> None:
    settings = Settings(blue_provider="openai_compatible", blue_base_url="")
    with pytest.raises(ProviderError) as error:
        ProviderConfig.blue(settings)
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"


def test_client_constructor_is_the_second_line_of_defense() -> None:
    # Build a valid OpenAI-role config, then force the provider field past __post_init__
    # to simulate any future path that bypasses config validation.
    config = ProviderConfig(
        role_name="RED",
        provider="openai",
        base_url="",
        api_key="local",
        model="m",
    )
    object.__setattr__(config, "provider", "openai_compatible")
    with pytest.raises(ProviderError) as error:
        OpenAICompatibleProvider(config)
    assert error.value.code == "RED_PROVIDER_UNAVAILABLE"


def test_openai_role_falls_back_to_the_shared_hosted_key() -> None:
    # Settings.has_blue treats OPENAI_API_KEY as valid; the provider must too, or it
    # would send the placeholder 'local' key to api.openai.com.
    settings = Settings(
        blue_provider="openai",
        blue_api_key="",
        openai_api_key="sk-hosted",
        blue_model="gpt-4.1-mini",
    )
    config = ProviderConfig.blue(settings)
    assert config.api_key == "sk-hosted"


def test_openai_role_prefers_its_own_key_over_the_shared_one() -> None:
    settings = Settings(
        blue_provider="openai",
        blue_api_key="sk-role",
        openai_api_key="sk-hosted",
        blue_model="gpt-4.1-mini",
    )
    assert ProviderConfig.blue(settings).api_key == "sk-role"


def test_openai_role_without_any_key_is_refused() -> None:
    settings = Settings(red_provider="openai", red_api_key="", openai_api_key="", red_model="gpt-4.1-mini")
    with pytest.raises(ProviderError) as error:
        ProviderConfig.red(settings)
    assert error.value.code == "RED_PROVIDER_UNAVAILABLE"
    assert "placeholder" in error.value.message


def test_compatible_role_keeps_its_placeholder_key() -> None:
    # Local servers need no key; a compatible role must not require the hosted one.
    settings = Settings(
        blue_provider="openai_compatible",
        blue_base_url="http://127.0.0.1:11434/v1",
        blue_api_key="",
        openai_api_key="",
    )
    assert ProviderConfig.blue(settings).api_key == ""


def test_model_layer_does_not_import_the_provider_layer() -> None:
    """Pin the import layering that the audit->red->providers->audit cycle broke.

    Importing the model packages alone must not pull in ``app.coevolution.providers``.
    If a model module ever imports the provider layer again, the chain
    providers -> models.audit -> models.red -> providers becomes circular.
    """
    program = (
        "import app.models.red, app.models.audit, sys; "
        "print('app.coevolution.providers' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", "model layer must not import app.coevolution.providers"


def _openrouter_settings(**overrides: object) -> SimpleNamespace:
    """Settings-like stand-in so these tests do not depend on config.py's evolving fields."""
    values: dict[str, object] = {
        "blue_provider": "openrouter",
        "blue_base_url": "https://openrouter.ai/api/v1",
        "blue_api_key": "",
        "blue_model": "openai/gpt-4.1-mini",
        "openai_api_key": SecretStr(""),
        "openrouter_api_key": SecretStr("sk-or-test"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_openrouter_uses_the_dedicated_key() -> None:
    config = ProviderConfig.blue(_openrouter_settings())
    assert config.provider == "openrouter"
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.api_key == "sk-or-test"


def test_openrouter_never_falls_back_to_the_openai_key() -> None:
    settings = _openrouter_settings(
        openrouter_api_key=SecretStr(""), openai_api_key=SecretStr("sk-openai")
    )
    with pytest.raises(ProviderError) as error:
        ProviderConfig.blue(settings)
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"
    assert "OPENROUTER_API_KEY" in error.value.message
    assert "sk-openai" not in error.value.message


def test_openrouter_requires_an_explicit_base_url() -> None:
    settings = _openrouter_settings(blue_base_url="")
    with pytest.raises(ProviderError) as error:
        ProviderConfig.blue(settings)
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"
    assert "base_url" in error.value.message


async def test_openrouter_key_is_never_leaked_in_errors_or_the_ledger() -> None:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model="openai/gpt-4.1-mini",
    )
    provider = OpenAICompatibleProvider(config)

    class Boom:
        async def create(self, **_kwargs: object) -> object:
            raise RuntimeError("401 for Authorization: Bearer sk-or-secret")

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Boom()))  # type: ignore[assignment]
    with pytest.raises(ProviderError) as error:
        await provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            run_id="T-LEAK",
            generation=0,
            role="red_attacker",
        )
    assert "sk-or-secret" not in str(error.value), "the key leaked into the raised error"
    assert provider.calls, "the failed call must still be recorded"
    assert all("sk-or-secret" not in (call.error or "") for call in provider.calls), "the key leaked into the ledger"


class _JsonProbe(BaseModel):
    ok: bool
    note: str = ""


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str, model: str = "test-model") -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = None
        self.model = model


def _completions_script(seen: list[bool], content: str) -> type:
    class Script:
        async def create(self, **kwargs: object) -> _FakeCompletion:
            seen.append("response_format" in kwargs)
            if "response_format" in kwargs:
                raise RuntimeError("response_format is not supported for this model")
            return _FakeCompletion(content)

    return Script


async def test_structured_output_degrades_when_response_format_is_rejected() -> None:
    """Models that reject ``response_format`` fall back to text mode + extraction/repair."""
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="thinkingmachines/inkling:free",
    )
    provider = OpenAICompatibleProvider(config)
    seen: list[bool] = []
    provider.client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=_completions_script(seen, '{"ok": true, "note": "text mode"}')())
    )
    value, _ = await provider.structured_output(
        schema=_JsonProbe,
        system="s",
        user="u",
        run_id="T-JSONMODE",
        generation=0,
        role="blue_executor",
    )
    assert value.ok is True and value.note == "text mode"
    assert seen[0] is True, "the first attempt must try JSON mode"
    assert False in seen, "the retry must omit response_format"


async def test_structured_output_degrades_when_provider_names_structured_outputs() -> None:
    """Novita/OpenRouter names the feature 'structured-outputs'; it must still degrade once."""

    class Script:
        def __init__(self) -> None:
            self.seen: list[bool] = []

        async def create(self, **kwargs: object) -> _FakeCompletion:
            self.seen.append("response_format" in kwargs)
            if "response_format" in kwargs:
                raise RuntimeError("does not support feature: structured-outputs")
            return _FakeCompletion('{"ok": true, "note": "text mode"}')

    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="inclusionai/ling-3.0-flash-fin:free",
    )
    provider = OpenAICompatibleProvider(config)
    script = Script()
    provider.client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=script)
    )
    value, _ = await provider.structured_output(
        schema=_JsonProbe,
        system="s",
        user="u",
        run_id="T-STRUCTURED",
        generation=0,
        role="blue_executor",
    )
    assert value.ok is True and value.note == "text mode"
    assert script.seen == [True, False], "exactly one text-mode retry"


async def test_structured_output_does_not_swallow_unrelated_provider_errors() -> None:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="thinkingmachines/inkling:free",
    )
    provider = OpenAICompatibleProvider(config)

    class Boom:
        async def create(self, **_kwargs: object) -> object:
            raise RuntimeError("connection refused")

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Boom()))  # type: ignore[assignment]
    with pytest.raises(ProviderError) as error:
        await provider.structured_output(
            schema=_JsonProbe,
            system="s",
            user="u",
            run_id="T-NOFALLBACK",
            generation=0,
            role="blue_executor",
        )
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"


class _ProbeScript:
    """Records budgets and returns empty content below the escalation threshold."""

    def __init__(self, threshold: int = 512) -> None:
        self.threshold = threshold
        self.budgets: list[int] = []

    async def chat(self, **kwargs: object) -> ChatResult:
        budget = int(str(kwargs["max_tokens"]))
        self.budgets.append(budget)
        if budget < self.threshold:
            raise ProviderError("BLUE_PROVIDER_EMPTY_RESPONSE", "empty completion")
        return ChatResult(text="READY", latency_ms=7, usage={}, raw="READY", call_id="")


def _patch_provider(monkeypatch: pytest.MonkeyPatch, script: _ProbeScript) -> None:
    class Fake:
        def __init__(self, _config: object) -> None:
            pass

        async def chat(self, **kwargs: object) -> ChatResult:
            return await script.chat(**kwargs)

    monkeypatch.setattr("app.coevolution.providers.OpenAICompatibleProvider", Fake)


async def test_model_call_records_the_resolved_model_not_the_route() -> None:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="openrouter/free",
    )
    provider = OpenAICompatibleProvider(config)

    class Completions:
        async def create(self, **_kwargs: object) -> _FakeCompletion:
            return _FakeCompletion('{"ok": true}', model="dots-studio/dots-3-note-preview:free")

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))  # type: ignore[assignment]
    await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-ROUTE",
        generation=0,
        role="blue_executor",
    )
    # The route name stays available on the config/description, while the ledger records
    # the model that actually answered.
    assert provider.model == "openrouter/free"
    assert "openrouter/free" in provider.description
    assert provider.calls[-1].model == "dots-studio/dots-3-note-preview:free"


async def test_probe_escalates_budget_when_a_free_route_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _ProbeScript()
    _patch_provider(monkeypatch, script)
    result = await probe(
        ProviderConfig(
            role_name="BLUE",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-x",
            model="openrouter/free",
        )
    )
    assert result.reachable is True
    assert script.budgets == [128, 1024]


async def test_probe_does_not_retry_a_hard_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class Fake:
        def __init__(self, _config: object) -> None:
            pass

        async def chat(self, **_kwargs: object) -> ChatResult:
            calls["count"] += 1
            raise ProviderError("BLUE_PROVIDER_UNAVAILABLE", "connection refused")

    monkeypatch.setattr("app.coevolution.providers.OpenAICompatibleProvider", Fake)
    result = await probe(
        ProviderConfig(
            role_name="BLUE",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-x",
            model="openrouter/free",
        )
    )
    assert result.reachable is False
    assert calls["count"] == 1, "a hard failure must not be retried"


async def test_empty_task_completion_still_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An always-empty task retries bounded (2) then fails closed; nothing hidden."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.coevolution.providers._sleep", fake_sleep)
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="openrouter/free",
    )
    provider = OpenAICompatibleProvider(config)
    calls = {"n": 0}

    class Empty:
        async def create(self, **_kwargs: object) -> _FakeCompletion:
            calls["n"] += 1
            return _FakeCompletion("")

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Empty()))  # type: ignore[assignment]
    with pytest.raises(ProviderError) as error:
        await provider.chat(
            messages=[{"role": "user", "content": "do the task"}],
            run_id="T-EMPTY",
            generation=0,
            role="blue_executor",
            max_tokens=4096,
        )
    assert error.value.code == "BLUE_PROVIDER_EMPTY_RESPONSE"
    assert calls["n"] == 3, "1 initial + 2 bounded empty retries"
    assert len(sleeps) == 2
    errors = [call.error for call in provider.calls]
    assert errors[0] is not None and errors[0].startswith("empty completion") and "retry 1/2" in errors[0]
    assert "max_tokens=8192" in errors[0], "the first retry must raise the budget"
    assert errors[1] is not None and "retry 2/2" in errors[1] and "max_tokens=12000" in errors[1]
    assert errors[2] is not None and errors[2].startswith("empty completion") and "retry" not in errors[2]


async def test_chat_retries_empty_completion_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.coevolution.providers._sleep", fake_sleep)
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="openrouter/free",
    )
    provider = OpenAICompatibleProvider(config)
    sequence = [_FakeCompletion(""), _FakeCompletion("READY")]
    calls = {"n": 0}

    class Seq:
        async def create(self, **_kwargs: object) -> _FakeCompletion:
            index = calls["n"]
            calls["n"] += 1
            return sequence[min(index, len(sequence) - 1)]

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Seq()))  # type: ignore[assignment]
    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-EMPTYOK",
        generation=0,
        role="blue_executor",
    )
    assert result.text == "READY"
    assert calls["n"] == 2
    errors = [call.error for call in provider.calls]
    assert errors[0] is not None and errors[0].startswith("empty completion") and "retry 1/2" in errors[0]
    assert "max_tokens=" in errors[0], "the empty retry must escalate the budget"
    assert errors[1] is None
    assert len(sleeps) == 1


async def test_chat_treats_tool_calls_as_non_empty() -> None:
    """content=null with tool_calls present must NOT trigger the empty retry."""
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="openrouter/free",
    )
    provider = OpenAICompatibleProvider(config)

    class ToolMessage:
        def __init__(self) -> None:
            self.content = None
            self.tool_calls = [
                SimpleNamespace(id="c1", function=SimpleNamespace(name="send_email"))
            ]

    class ToolCompletion:
        def __init__(self) -> None:
            self.choices = [SimpleNamespace(message=ToolMessage())]
            self.usage = None
            self.model = "test-model"

    calls = {"n": 0}

    class ToolScript:
        async def create(self, **_kwargs: object) -> ToolCompletion:
            calls["n"] += 1
            return ToolCompletion()

    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=ToolScript()))  # type: ignore[assignment]
    await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-TOOLS",
        generation=0,
        role="blue_executor",
    )
    assert calls["n"] == 1, "a tool call is a non-empty turn"
    assert provider.calls[0].error is None


def test_provider_timeout_can_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_TIMEOUT_SECONDS", "300")
    settings = Settings(
        red_provider="openai_compatible",
        red_base_url="http://127.0.0.1:9/v1",
        red_model="m",
        red_api_key="local",
        blue_provider="openai_compatible",
        blue_base_url="http://127.0.0.1:9/v1",
        blue_model="m",
        blue_api_key="local",
    )
    assert ProviderConfig.red(settings).timeout_seconds == 300.0
    assert ProviderConfig.blue(settings).timeout_seconds == 300.0


def test_provider_timeout_defaults_to_120(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVIDER_TIMEOUT_SECONDS", raising=False)
    settings = Settings(
        red_provider="openai_compatible",
        red_base_url="http://127.0.0.1:9/v1",
        red_model="m",
        red_api_key="local",
    )
    assert ProviderConfig.red(settings).timeout_seconds == 120.0


def _http_error(
    status: int, retry_after: float | None = None, reset_epoch: float | None = None
) -> Exception:
    error = Exception(f"HTTP {status}")
    error.status_code = status  # type: ignore[attr-defined]
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers["retry-after"] = str(retry_after)
    if reset_epoch is not None:
        headers["x-ratelimit-reset"] = str(reset_epoch)
    error.response = SimpleNamespace(headers=headers)  # type: ignore[attr-defined]
    return error


class _Scripted:
    """Returns/raises a scripted sequence; the final behavior repeats forever."""

    def __init__(self, behaviors: list[object]) -> None:
        self.behaviors = behaviors
        self.calls = 0

    async def create(self, **_kwargs: object) -> object:
        behavior = self.behaviors[min(self.calls, len(self.behaviors) - 1)]
        self.calls += 1
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


def _scripted_provider(script: _Scripted) -> OpenAICompatibleProvider:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="inclusionai/ling-3.0-flash-fin:free",
    )
    provider = OpenAICompatibleProvider(config)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=script))  # type: ignore[assignment]
    return provider


def _patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("app.coevolution.providers._sleep", fake_sleep)
    return delays


async def test_chat_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    provider = _scripted_provider(_Scripted([_http_error(429), _FakeCompletion("READY")]))
    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-429",
        generation=0,
        role="blue_executor",
    )
    assert result.text == "READY"
    assert len(provider.calls) == 2, "every attempt must be persisted"
    assert provider.calls[0].error == "429 retry 1/5"
    assert provider.calls[1].error is None
    assert len(delays) == 1


async def test_chat_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sleep(monkeypatch)
    provider = _scripted_provider(_Scripted([_http_error(503), _FakeCompletion("READY")]))
    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-503",
        generation=0,
        role="blue_executor",
    )
    assert result.text == "READY"
    assert provider.calls[0].error == "503 retry 1/4"


async def test_chat_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    provider = _scripted_provider(_Scripted([_http_error(429)]))
    with pytest.raises(ProviderError) as error:
        await provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            run_id="T-EXHAUST",
            generation=0,
            role="blue_executor",
        )
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"
    assert len(provider.calls) == 6, "1 initial + 5 retries (429)"
    assert [call.error for call in provider.calls[:5]] == [f"429 retry {n}/5" for n in (1, 2, 3, 4, 5)]
    assert "HTTP 429" in (provider.calls[-1].error or "")
    assert len(delays) == 5
    # exponential: 2s, 4s, 8s, 16s, then capped at 30s
    assert delays[0] >= 2.0 and delays[1] >= 4.0 and delays[2] >= 8.0 and delays[3] >= 16.0
    assert delays[4] == 30.0


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
async def test_chat_does_not_retry_auth_or_validation(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    delays = _patch_sleep(monkeypatch)
    provider = _scripted_provider(_Scripted([_http_error(status)]))
    with pytest.raises(ProviderError) as error:
        await provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            run_id="T-NORETRY",
            generation=0,
            role="blue_executor",
        )
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"
    assert len(provider.calls) == 1, f"HTTP {status} must not be retried"
    assert delays == []


async def test_chat_honors_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    provider = _scripted_provider(
        _Scripted([_http_error(429, retry_after=7), _FakeCompletion("READY")])
    )
    result = await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-RETRYAFTER",
        generation=0,
        role="blue_executor",
    )
    assert result.text == "READY"
    assert delays == [7.0]


async def test_chat_honors_retry_after_on_5xx_too(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    provider = _scripted_provider(
        _Scripted([_http_error(503, retry_after=11), _FakeCompletion("READY")])
    )
    await provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        run_id="T-503RA",
        generation=0,
        role="blue_executor",
    )
    assert delays == [11.0]


async def test_completion_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The BlueExecutor-shaped path (raw SDK call with tools) now retries too."""
    delays = _patch_sleep(monkeypatch)
    script = _Scripted([_http_error(429), _FakeCompletion("ok")])
    provider = _scripted_provider(script)
    response = await provider.completion(
        run_id="T-EXEC",
        generation=0,
        role="blue_executor",
        model="inclusionai/ling-3.0-flash-fin:free",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "send_email"}}],
        temperature=0.4,
        max_tokens=64,
    )
    assert response.choices[0].message.content == "ok"
    assert script.calls == 2
    assert provider.calls[0].error == "429 retry 1/5"
    # completion leaves the accepted-outcome row to the caller (record_external_call).
    assert len(provider.calls) == 1
    assert delays != []


async def test_completion_honors_rate_limit_reset_header_and_caps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = _patch_sleep(monkeypatch)
    near = int((time.time() + 5) * 1000)
    provider = _scripted_provider(_Scripted([_http_error(429, reset_epoch=near), _FakeCompletion("ok")]))
    await provider.completion(
        run_id="T-RESET", role="blue_executor", model="m", messages=[{"role": "user", "content": "hi"}]
    )
    assert 3.5 <= delays[0] <= 6.0, delays

    delays.clear()
    far = int((time.time() + 600) * 1000)
    provider2 = _scripted_provider(_Scripted([_http_error(429, reset_epoch=far), _FakeCompletion("ok")]))
    await provider2.completion(
        run_id="T-CAP", role="blue_executor", model="m", messages=[{"role": "user", "content": "hi"}]
    )
    assert delays[0] == 120.0, delays


async def test_completion_reads_reset_from_the_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    error = _http_error(429)
    reset_ms = int((time.time() + 9) * 1000)
    error.body = {  # type: ignore[attr-defined]
        "error": {"metadata": {"raw": f'{{"X-RateLimit-Reset": {reset_ms}}}'}}
    }
    provider = _scripted_provider(_Scripted([error, _FakeCompletion("ok")]))
    await provider.completion(
        run_id="T-BODY", role="blue_executor", model="m", messages=[{"role": "user", "content": "hi"}]
    )
    assert 7.0 <= delays[0] <= 10.0, delays


async def test_completion_does_not_retry_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    delays = _patch_sleep(monkeypatch)
    script = _Scripted([_http_error(401)])
    provider = _scripted_provider(script)
    with pytest.raises(ProviderError) as error:
        await provider.completion(
            run_id="T-AUTH",
            role="blue_executor",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert error.value.code == "BLUE_PROVIDER_UNAVAILABLE"
    assert script.calls == 1
    assert delays == []
    # The caller records the terminal row; completion only records retry attempts.
    assert provider.calls == []


class _ThresholdBudgetScript:
    """Empty below a max_tokens threshold, content at or above it; records every budget."""

    def __init__(self, threshold: int, content: str) -> None:
        self.threshold = threshold
        self.content = content
        self.tokens: list[int] = []

    async def create(self, **kwargs: object) -> _FakeCompletion:
        tokens = int(str(kwargs.get("max_tokens", 0)))
        self.tokens.append(tokens)
        return _FakeCompletion(self.content if tokens >= self.threshold else "")


def _budget_provider(script: object) -> OpenAICompatibleProvider:
    config = ProviderConfig(
        role_name="BLUE",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-x",
        model="inclusionai/ling-3.0-flash-fin:free",
    )
    provider = OpenAICompatibleProvider(config)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=script))  # type: ignore[assignment]
    return provider


async def test_structured_output_escalates_budget_on_empty_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chat() escalates the budget in place; the retry succeeds once the budget is 6000."""
    _patch_sleep(monkeypatch)
    script = _ThresholdBudgetScript(6000, '{"ok": true, "note": "escalated"}')
    provider = _budget_provider(script)
    value, _ = await provider.structured_output(
        schema=_JsonProbe,
        system="s",
        user="u",
        run_id="T-ESC",
        generation=0,
        role="blue_executor",
        max_tokens=3000,
    )
    assert value.ok is True and value.note == "escalated"
    assert script.tokens == [3000, 6000]
    errors = [call.error for call in provider.calls]
    assert errors[0] is not None and "retry 1/2" in errors[0] and "max_tokens=6000" in errors[0]
    assert errors[1] is None


async def test_structured_output_fails_closed_after_empty_budget_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Always-empty: bounded escalation 3000 -> 6000 -> 12000, then raises."""
    _patch_sleep(monkeypatch)
    script = _ThresholdBudgetScript(10**9, "never")
    provider = _budget_provider(script)
    with pytest.raises(ProviderError) as error:
        await provider.structured_output(
            schema=_JsonProbe,
            system="s",
            user="u",
            run_id="T-ESC-FAIL",
            generation=0,
            role="blue_executor",
            max_tokens=3000,
        )
    assert error.value.code == "BLUE_PROVIDER_EMPTY_RESPONSE"
    assert script.tokens == [3000, 6000, 12000]
    assert len(provider.calls) == 3


async def test_structured_output_does_not_escalate_a_non_empty_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sleep(monkeypatch)
    script = _ThresholdBudgetScript(0, '{"ok": true, "note": "first"}')
    provider = _budget_provider(script)
    value, _ = await provider.structured_output(
        schema=_JsonProbe,
        system="s",
        user="u",
        run_id="T-NOESC",
        generation=0,
        role="blue_executor",
        max_tokens=3000,
    )
    assert value.note == "first"
    assert script.tokens == [3000]
    assert len(provider.calls) == 1
