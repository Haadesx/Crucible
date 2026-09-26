"""Two real model backends (Red and Blue) behind one OpenAI-compatible abstraction (§1, §6, §7, §32).

Every local server (llama.cpp, Ollama, vLLM) plus OpenAI/OpenRouter speaks the
`/chat/completions` dialect, so one client class covers them all. There is no mock
provider here: fake agents exist only under `tests/` or `TEST_MODE=true` (§33).
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, replace
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.models.audit import ModelCall, ModelRole, new_model_call_id

logger = logging.getLogger(__name__)

ProviderName = Literal["openai", "openai_compatible", "openrouter"]

# "auto" sends response_format=json_object first and degrades in place when the endpoint
# rejects it; "never" skips that known-unsupported request and goes straight to the
# validated text/JSON path (the parser/repairs are the same either way).
JsonMode = Literal["auto", "never"]

ModelT = TypeVar("ModelT", bound=BaseModel)


class ProviderError(Exception):
    """Raised when a real model endpoint is unavailable or returns unusable output (§33)."""

    def __init__(self, code: str, message: str, *, output_budget: int | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        # The final-output budget the failing attempt reached, when known. Lets the
        # structured-output caller escalate from what was actually spent instead of
        # from a stale value and doubling the retry count.
        self.output_budget = output_budget


def _secret_value(value: object) -> str:
    """Read a SecretStr/str/None safely; ``None`` reads as empty.

    Keeps the provider layer working whether or not a given Settings build has a
    particular optional credential field yet.
    """
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter())
    return str(value)


def _require_compatible_base_url(role_name: str, provider: ProviderName, base_url: str | None) -> None:
    """Fail closed when an OpenAI-compatible role has no endpoint (§6, §33).

    The OpenAI SDK treats a missing base_url as api.openai.com, so an empty value
    would silently ship the local/OpenRouter key to a hosted service instead of the
    configured endpoint. A blank string and None are both rejected. ``openrouter`` is
    held to the same rule: it is an explicit endpoint, never api.openai.com.
    """
    if provider in {"openai_compatible", "openrouter"} and not (base_url or "").strip():
        raise ProviderError(
            f"{role_name}_PROVIDER_UNAVAILABLE",
            f"{role_name} is configured as '{provider}' with an empty base_url. "
            "Set RED_BASE_URL/BLUE_BASE_URL to the real endpoint (for example the ai-rig "
            "Tailscale address, an SSH tunnel, or https://openrouter.ai/api/v1); refusing "
            "to fall through to api.openai.com.",
        )


def _resolve_api_key(
    *,
    role_name: str,
    provider: ProviderName,
    explicit: str,
    hosted: str,
    openrouter: str = "",
) -> str:
    """Resolve the key a role will authenticate with.

    * ``openai``: prefer the role key, then the shared OPENAI_API_KEY, matching
      ``Settings.has_blue``. Without this the client would substitute the harmless
      local placeholder ``local`` and send it to api.openai.com.
    * ``openrouter``: require the dedicated OPENROUTER_API_KEY. It must not fall back
      to OPENAI_API_KEY, a placeholder, or api.openai.com.
    * ``openai_compatible``: local servers need no key; the placeholder is unchanged.
    """
    if provider == "openai_compatible":
        return explicit
    if provider == "openrouter":
        key = (openrouter or "").strip()
        if not key:
            raise ProviderError(
                f"{role_name}_PROVIDER_UNAVAILABLE",
                f"{role_name} uses provider 'openrouter' but OPENROUTER_API_KEY is empty. "
                "Set it in the environment; refusing to fall back to OPENAI_API_KEY, a "
                "placeholder key, or api.openai.com.",
            )
        return key
    key = (explicit or "").strip() or (hosted or "").strip()
    if not key:
        raise ProviderError(
            f"{role_name}_PROVIDER_UNAVAILABLE",
            f"{role_name} uses provider 'openai' but no API key is configured. Set "
            "BLUE_API_KEY/RED_API_KEY or OPENAI_API_KEY; refusing to send a placeholder "
            "key to api.openai.com.",
        )
    return key


def _redact(secret: str, text: str) -> str:
    """Strip a credential from anything that could be logged or persisted (§33)."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _response_format_unsupported(error: Exception) -> bool:
    """True when an endpoint rejected the JSON-mode ``response_format`` request.

    Not every OpenAI-compatible model accepts ``response_format: json_object`` (for
    example OpenRouter's ``inclusionai/ling-3.0-flash-fin:free``, the configured engineer
    fallback, which returns HTTP 400 "does not support feature: structured-outputs").
    The prompt still asks for JSON and ``_extract_json``/repairs still validate it, so
    the caller degrades to text mode rather than failing the task; models known to reject
    it are configured with ``json_mode="never"`` so the rejected request is never sent.
    """
    text = str(error).lower()
    return (
        "response_format" in text
        or "json_object" in text
        or "json mode" in text
        or "structured-output" in text
        or "structured output" in text
        or "structured_output" in text
    )


# Bounded retry policy for transient upstream failures (§33). Retries are visible in the
# ledger (one ModelCall per attempt) because max_retries stays 0 on the SDK client.
_MAX_RETRIES = 4            # 5xx -> up to 5 attempts
_MAX_429_RETRIES = 5        # 429 -> up to 6 attempts (a free-tier minute can exceed 5 * 30s)
_BACKOFF_BASE_SECONDS = 2.0
_BACKOFF_FACTOR = 2.0
_BACKOFF_CAP_SECONDS = 30.0
_RATE_LIMIT_CAP_SECONDS = 120.0
_X_RATE_RESET_RE = re.compile(r"X-RateLimit-Reset[^0-9]{0,6}(\d+(?:\.\d+)?)", re.IGNORECASE)

# Empty completions on a reasoning model usually mean the thinking pass consumed the
# whole budget (finish_reason=length). structured_output escalates the budget a bounded
# number of times before failing closed.
_EMPTY_BUDGET_ESCALATIONS = 2
_EMPTY_BUDGET_CAP = 12_000
_MAX_EMPTY_RETRIES = 2        # an empty (no content, no tool_calls) turn retries like a transient


def _status_code(error: Exception) -> int | None:
    """HTTP status from an SDK error, whether exposed as an attribute or a response."""
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _is_retryable_status(status: int | None) -> bool:
    """Only 429 and 5xx are transient; auth/validation 4xx fail immediately."""
    return status == 429 or (status is not None and 500 <= status <= 599)


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _provider_timeout(settings: Settings) -> float:
    """Optional provider timeout override (Settings attr or PROVIDER_TIMEOUT_SECONDS env).

    ai-rig Red calls occasionally exceed 120s under single-slot load; the override has a
    safe default so an unset environment behaves exactly as before.
    """
    raw = getattr(settings, "provider_timeout_seconds", None)
    if raw in (None, ""):
        raw = os.environ.get("PROVIDER_TIMEOUT_SECONDS", "")
    value = _to_float(raw)
    return value if value is not None and value > 0 else 120.0


def _to_float(raw: object) -> float | None:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _rate_limit_reset_seconds(error: Exception) -> float | None:
    """Seconds to wait until ``X-RateLimit-Reset`` (ms epoch), from header or 429 body.

    OpenRouter reports a per-minute free-tier limit whose reset lands in the JSON body
    metadata rather than a ``Retry-After`` header; without this the capped exponential
    backoff can finish before the window reopens.
    """
    now = time.time()
    candidates: list[float] = []
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        parsed = _to_float(headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset"))
        if parsed is not None:
            candidates.append(parsed)
    body = getattr(error, "body", None)
    texts = [str(error)]
    if body is not None:
        texts.append(body if isinstance(body, str) else json.dumps(body, default=str))
    for text in texts:
        for match in _X_RATE_RESET_RE.finditer(text):
            parsed = _to_float(match.group(1))
            if parsed is not None:
                candidates.append(parsed)
    for value in candidates:
        if value > 1e11:  # milliseconds since epoch
            wait = value / 1000.0 - now
        elif value > 1e9:  # seconds since epoch
            wait = value - now
        else:  # already a relative duration
            wait = value
        if wait >= 0:
            return wait
    return None


def _backoff_seconds(retry: int) -> float:
    base = _BACKOFF_BASE_SECONDS * (_BACKOFF_FACTOR ** (retry - 1))
    return min(_BACKOFF_CAP_SECONDS, base + random.uniform(0.0, base * 0.1))


def _retry_delay(error: Exception, retry: int, status: int | None = None) -> float:
    """Retry-After (any status), else X-RateLimit-Reset for 429, else capped exponential + jitter."""
    retry_after = _retry_after_seconds(error)
    if retry_after is not None:
        cap = _RATE_LIMIT_CAP_SECONDS if status == 429 else _BACKOFF_CAP_SECONDS
        return max(0.0, min(retry_after, cap))
    if status == 429:
        reset = _rate_limit_reset_seconds(error)
        if reset is not None:
            return max(0.0, min(reset, _RATE_LIMIT_CAP_SECONDS))
    return _backoff_seconds(retry)


async def _sleep(seconds: float) -> None:
    """Indirection so tests can monkeypatch waiting without real time passing."""
    await asyncio.sleep(seconds)


@dataclass(frozen=True)
class ProviderConfig:
    role_name: str
    provider: ProviderName
    base_url: str | None
    api_key: str
    model: str
    timeout_seconds: float = 120.0
    json_mode: JsonMode = "auto"

    def __post_init__(self) -> None:
        # §6, §33: an OpenAI-compatible endpoint with no base_url must never be
        # usable. The OpenAI SDK silently defaults a missing base_url to
        # api.openai.com, so an empty value would send the "local" key to a hosted
        # service instead of the configured rig. Fail closed instead of falling
        # through. A blank string and None are both rejected.
        _require_compatible_base_url(self.role_name, self.provider, self.base_url)

    @property
    def is_local(self) -> bool:
        return (self.base_url is not None and "localhost" in self.base_url) or (
            self.base_url is not None and "127.0.0.1" in self.base_url
        )

    @classmethod
    def red(cls, settings: Settings) -> "ProviderConfig":
        return cls(
            role_name="RED",
            provider=settings.red_provider,
            base_url=settings.red_base_url or None,
            api_key=_resolve_api_key(
                role_name="RED",
                provider=settings.red_provider,
                explicit=settings.red_api_key,
                hosted=settings.openai_api_key.get_secret_value(),
                openrouter=_secret_value(getattr(settings, "openrouter_api_key", "")),
            ),
            model=settings.red_model,
            timeout_seconds=_provider_timeout(settings),
        )

    @classmethod
    def blue(cls, settings: Settings) -> "ProviderConfig":
        return cls(
            role_name="BLUE",
            provider=settings.blue_provider,
            base_url=settings.blue_base_url or None,
            api_key=_resolve_api_key(
                role_name="BLUE",
                provider=settings.blue_provider,
                explicit=settings.blue_api_key,
                hosted=settings.openai_api_key.get_secret_value(),
                openrouter=_secret_value(getattr(settings, "openrouter_api_key", "")),
            ),
            model=settings.blue_model,
            timeout_seconds=_provider_timeout(settings),
        )

    @classmethod
    def blue_engineer(cls, settings: Settings, model: str, *, json_mode: JsonMode) -> "ProviderConfig":
        """A harness-patch engineer config: Blue's endpoint/key with its own model.

        ``json_mode="never"`` is the capability-aware setting for a model known to reject
        ``response_format`` (Ling): the request the endpoint would 400 on is not sent at
        all, and the same validated text/JSON extraction and repair path runs instead.
        """

        return replace(cls.blue(settings), model=model, json_mode=json_mode)


@dataclass(frozen=True)
class ChatResult:
    text: str
    latency_ms: int
    usage: dict[str, Any]
    raw: str
    call_id: str = ""
    # Why the model stopped; "length" means the budget was exhausted. Kept separate from
    # the text so a truncated final answer can trigger a budget escalation without ever
    # touching hidden reasoning.
    finish_reason: str = ""


class OpenAICompatibleProvider:
    """Thin async chat-completions client that persists a ModelCall for every request."""

    def __init__(self, config: ProviderConfig) -> None:
        # Defense in depth: even a hand-built config must not reach the SDK with an
        # empty base_url for an OpenAI-compatible role (§6, §33).
        _require_compatible_base_url(config.role_name, config.provider, config.base_url)
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key or "local",
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            max_retries=0,
        )
        self.calls: list[ModelCall] = []

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def description(self) -> str:
        location = self.config.base_url or "api.openai.com"
        return f"{self.config.provider}:{self.config.model} @ {location}"

    async def _create_with_retry(
        self,
        request_body: dict[str, Any],
        ledger: dict[str, Any],
        *,
        record_terminal_failure: bool = True,
    ) -> tuple[Any, int]:
        """One SDK call wrapped in the shared bounded retry/backoff policy.

        Retry attempts are persisted as ModelCall rows. ``record_terminal_failure`` is
        True for ``chat`` (which owns its whole ledger) and False for ``completion``
        (whose caller records the accepted outcome via ``record_external_call``), so a
        terminal failure is never double-counted.
        """
        payload_hash = hashlib.sha256(
            json.dumps(request_body.get("messages"), sort_keys=True, default=str).encode()
        ).hexdigest()
        prompt_chars = sum(
            len(str(message.get("content", ""))) for message in request_body.get("messages", [])
        )
        retries = 0
        while True:
            started = time.perf_counter()
            try:
                response = await self.client.chat.completions.create(**request_body)
            except Exception as exc:
                latency = int((time.perf_counter() - started) * 1_000)
                status = _status_code(exc)
                max_retries = _MAX_429_RETRIES if status == 429 else _MAX_RETRIES
                if _is_retryable_status(status) and retries < max_retries:
                    retries += 1
                    # One ledger row per attempt: the retry history is never hidden.
                    self._record(
                        **ledger,
                        input_hash=payload_hash,
                        prompt_chars=prompt_chars,
                        output_text="",
                        latency_ms=latency,
                        usage={},
                        error=f"{status} retry {retries}/{max_retries}",
                    )
                    await _sleep(_retry_delay(exc, retries, status))
                    continue
                # Never let a credential reach the ledger or the raised error (§33).
                failure = _redact(self.config.api_key, f"{type(exc).__name__}: {exc}")
                if record_terminal_failure:
                    self._record(
                        **ledger,
                        input_hash=payload_hash,
                        prompt_chars=prompt_chars,
                        output_text="",
                        latency_ms=latency,
                        usage={},
                        error=failure[:300],
                    )
                raise ProviderError(
                    f"{self.config.role_name}_PROVIDER_UNAVAILABLE",
                    f"{self.description} failed after {latency}ms: {failure}",
                ) from exc
            return response, int((time.perf_counter() - started) * 1_000)

    async def completion(
        self,
        *,
        retry: bool = True,
        run_id: str = "",
        generation: int = 0,
        role: ModelRole = "blue_executor",
        agent_version_id: str = "",
        artifact_id: str = "",
        artifact_type: str = "",
        **kwargs: Any,
    ) -> Any:
        """Raw SDK chat-completions call under the same bounded retry policy as ``chat``.

        Used by callers that need the raw response (e.g. BlueExecutor tool turns). Retry
        attempts are recorded as ModelCall rows; the caller owns the accepted outcome's
        ledger row via ``record_external_call`` so roles/artifacts stay intact.
        """
        if not retry:
            return await self.client.chat.completions.create(**kwargs)
        ledger: dict[str, Any] = {
            "run_id": run_id,
            "generation": generation,
            "role": role,
            "agent_version_id": agent_version_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
        }
        response, _ = await self._create_with_retry(kwargs, ledger, record_terminal_failure=False)
        return response

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        run_id: str,
        generation: int,
        role: ModelRole,
        agent_version_id: str = "",
        artifact_id: str = "",
        artifact_type: str = "",
        temperature: float = 0.8,
        max_tokens: int = 1_200,
        json_mode: bool = False,
    ) -> ChatResult:
        request_body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}
        ledger: dict[str, Any] = {
            "run_id": run_id,
            "generation": generation,
            "role": role,
            "agent_version_id": agent_version_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
        }
        payload_hash = hashlib.sha256(
            json.dumps(request_body.get("messages"), sort_keys=True, default=str).encode()
        ).hexdigest()
        prompt_chars = sum(len(str(message.get("content", ""))) for message in messages)
        empty_retries = 0
        budget = max_tokens
        while True:
            request_body["max_tokens"] = budget
            response, latency = await self._create_with_retry(request_body, ledger)
            choice = response.choices[0] if response.choices else None
            message = choice.message if choice is not None else None
            text = (getattr(message, "content", None) or "") if message is not None else ""
            tool_calls = getattr(message, "tool_calls", None) or []
            finish_reason = str(getattr(choice, "finish_reason", "") or "") if choice is not None else ""
            if text.strip() or tool_calls:
                break
            # Empty visible answer (no content, no tool_calls). A reasoning model that
            # spent the whole budget thinking lands here with finish_reason=length and
            # its thoughts in reasoning_content; that is a budget problem, not an
            # unusable model. The hidden reasoning is never treated as the answer and
            # never persisted — only the condition (finish_reason, reasoning size) is.
            condition = _empty_completion_condition(
                finish_reason=finish_reason, reasoning_chars=len(_reasoning_text(message))
            )
            if empty_retries < _MAX_EMPTY_RETRIES and budget < _EMPTY_BUDGET_CAP:
                empty_retries += 1
                budget = min(budget * 2, _EMPTY_BUDGET_CAP)
                self._record(
                    **ledger,
                    input_hash=payload_hash,
                    prompt_chars=prompt_chars,
                    output_text="",
                    latency_ms=latency,
                    usage=self._usage(response),
                    resolved_model=str(getattr(response, "model", "") or ""),
                    error=f"{condition} retry {empty_retries}/{_MAX_EMPTY_RETRIES} with max_tokens={budget}",
                )
                await _sleep(_backoff_seconds(empty_retries))
                continue
            self._record(
                **ledger,
                input_hash=payload_hash,
                prompt_chars=prompt_chars,
                output_text="",
                latency_ms=latency,
                usage=self._usage(response),
                resolved_model=str(getattr(response, "model", "") or ""),
                error=condition,
            )
            raise ProviderError(
                f"{self.config.role_name}_PROVIDER_EMPTY_RESPONSE",
                f"{self.description} returned an empty completion ({condition})",
                output_budget=budget,
            )
        usage = self._usage(response)
        call = self._record(
            **ledger,
            input_hash=payload_hash,
            prompt_chars=prompt_chars,
            output_text=text[:4_000],
            latency_ms=latency,
            usage=usage,
            resolved_model=str(getattr(response, "model", "") or ""),
        )
        return ChatResult(
            text=text, latency_ms=latency, usage=usage, raw=text, call_id=call.id, finish_reason=finish_reason
        )

    async def structured_output(
        self,
        *,
        schema: type[ModelT],
        system: str,
        user: str,
        run_id: str,
        generation: int,
        role: ModelRole,
        agent_version_id: str = "",
        artifact_id: str = "",
        artifact_type: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1_600,
        repairs: int = 2,
        validate: Callable[[ModelT], str | None] | None = None,
    ) -> tuple[ModelT, ChatResult]:
        """JSON-mode request with deterministic extraction and bounded repair rounds (§10).

        A model that cannot produce schema-valid output is a loud failure, never a
        silent substitution; the repair prompt carries the concrete validation error.

        ``validate`` adds an application-level check that pydantic cannot express — a
        patch naming a stage the compiler cannot emit, say. It returns a reason string
        to reject the value, or None to accept it, and that reason reaches the model in
        the next repair round exactly like a schema error does. Without it a model can
        only learn its output was wrong by never being told what was wrong with it.
        """
        conversation: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_error = "response was not JSON"
        # Capability-aware start: a model known to reject response_format never sees it.
        json_mode = self.config.json_mode != "never"
        budget = max_tokens
        escalations = 0

        async def request(mode: bool, attempt: int) -> ChatResult:
            return await self.chat(
                messages=conversation,
                run_id=run_id,
                generation=generation,
                role=role,
                agent_version_id=agent_version_id,
                artifact_id=artifact_id,
                artifact_type=artifact_type if attempt == 0 else f"{artifact_type}:repair{attempt}" if artifact_type else f"repair{attempt}",
                temperature=temperature if attempt == 0 else 0.0,
                max_tokens=budget,
                json_mode=mode,
            )

        async def exchange(attempt: int) -> ChatResult:
            """One exchange, degrading JSON mode once and escalating an empty budget.

            An endpoint that rejects response_format is not a provider outage; a length-
            truncated empty completion is not an unusable model — it is a budget problem.
            Both are retried in place (bounded) rather than counted as a repair round.
            """
            nonlocal json_mode, budget, escalations
            mode = json_mode
            while True:
                try:
                    return await request(mode, attempt)
                except ProviderError as exc:
                    if mode and _response_format_unsupported(exc):
                        mode = False
                        json_mode = False
                        continue
                    if exc.output_budget is not None:
                        budget = max(budget, exc.output_budget)
                    if (
                        exc.code.endswith("_PROVIDER_EMPTY_RESPONSE")
                        and escalations < _EMPTY_BUDGET_ESCALATIONS
                        and budget < _EMPTY_BUDGET_CAP
                    ):
                        escalations += 1
                        budget = min(budget * 2, _EMPTY_BUDGET_CAP)
                        continue
                    raise

        for attempt in range(repairs + 1):
            result = await exchange(attempt)
            parsed = _extract_json(result.text)
            if parsed is not None:
                try:
                    value = schema.model_validate(parsed)
                except ValidationError as error:
                    last_error = str(error)[:600]
                else:
                    if validate is None:
                        return value, result
                    rejection = validate(value)
                    if rejection is None:
                        return value, result
                    last_error = rejection[:600]
            else:
                last_error = "response contained no JSON object"
            if attempt == repairs:
                break
            # A truncated final answer is a budget problem: raise the ceiling for the
            # repair round instead of asking again for a JSON object the model cannot
            # finish writing (bounded by the same cap as the empty-completion path).
            if result.finish_reason == "length" and budget < _EMPTY_BUDGET_CAP:
                budget = min(budget * 2, _EMPTY_BUDGET_CAP)
            conversation = [
                *conversation,
                {"role": "assistant", "content": result.text[:4_000]},
                {
                    "role": "user",
                    "content": (
                        "That output was rejected by the application's validator.\n"
                        f"Validation error: {last_error}\n"
                        f"Required top-level fields: {list(schema.model_fields.keys())}.\n"
                        "Fix exactly that problem and reply with ONLY the corrected JSON object."
                    ),
                },
            ]
        raise ProviderError(
            f"{self.config.role_name}_PROVIDER_UNUSABLE_OUTPUT",
            f"{self.description} did not return schema-valid JSON after {repairs} repair(s): {last_error}",
        )

    def record_external_call(
        self,
        *,
        run_id: str,
        generation: int,
        role: ModelRole,
        messages: list[dict[str, str]],
        text: str,
        latency_ms: int,
        usage: dict[str, Any],
        agent_version_id: str = "",
        artifact_id: str = "",
        artifact_type: str = "",
        error: str | None = None,
    ) -> ModelCall:
        """Ledger entry for a call made directly through the client (e.g. tool-calling turns)."""
        payload_hash = hashlib.sha256(
            json.dumps(messages, sort_keys=True, default=str).encode()
        ).hexdigest()
        return self._record(
            run_id=run_id,
            generation=generation,
            role=role,
            agent_version_id=agent_version_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            input_hash=payload_hash,
            prompt_chars=sum(len(str(message.get("content", ""))) for message in messages),
            output_text=text[:4_000],
            latency_ms=latency_ms,
            usage=usage,
            error=error,
        )

    def _record(self, **fields: Any) -> ModelCall:
        # ModelCall.model records the model that actually answered when the endpoint
        # reports one (OpenRouter resolves e.g. `openrouter/free` to a concrete model),
        # while config.model keeps the requested route name.
        resolved_model = str(fields.pop("resolved_model", "") or "")
        call = ModelCall(
            id=new_model_call_id(),
            provider=self.config.provider,
            base_url=self.config.base_url,
            model=resolved_model or self.config.model,
            role=cast(ModelRole, fields.pop("role")),
            input_hash=fields.pop("input_hash"),
            **fields,
        )
        self.calls.append(call)
        return call

    @staticmethod
    def _usage(response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }


class BlueEngineerProvider:
    """Harness-patch engineer with an explicit, non-racing fallback.

    The primary model authors the patch. The fallback runs only when the primary fails
    outright — transport, unavailable, rate-limited after the provider's own bounded
    retries, or unusable output after the normal repair rounds — so exactly one model
    authors each accepted patch, and every failed primary attempt stays visible as its
    own ledger row. Both providers are never queried concurrently, and the authoring
    model is whatever the accepted call row says it was.
    """

    def __init__(
        self,
        primary: OpenAICompatibleProvider,
        fallback: OpenAICompatibleProvider | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.fallbacks = 0

    @property
    def model(self) -> str:
        return self.primary.model

    @property
    def description(self) -> str:
        if self.fallback is None:
            return self.primary.description
        return f"{self.primary.description} (fallback {self.fallback.description})"

    @property
    def calls(self) -> list[ModelCall]:
        """Both providers' rows in call order; the fallback never runs before the primary."""
        merged = (
            [*self.primary.calls, *self.fallback.calls]
            if self.fallback is not None
            else [*self.primary.calls]
        )
        return sorted(merged, key=lambda call: call.created_at)

    async def structured_output(
        self,
        *,
        schema: type[ModelT],
        system: str,
        user: str,
        run_id: str,
        generation: int,
        role: ModelRole,
        agent_version_id: str = "",
        artifact_id: str = "",
        artifact_type: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1_600,
        repairs: int = 2,
        validate: Callable[[ModelT], str | None] | None = None,
    ) -> tuple[ModelT, ChatResult]:
        try:
            return await self.primary.structured_output(
                schema=schema, system=system, user=user, run_id=run_id, generation=generation,
                role=role, agent_version_id=agent_version_id, artifact_id=artifact_id,
                artifact_type=artifact_type, temperature=temperature, max_tokens=max_tokens,
                repairs=repairs, validate=validate,
            )
        except ProviderError as exc:
            if self.fallback is None:
                raise
            self.fallbacks += 1
            logger.warning(
                "blue engineer fallback %s -> %s after %s: %s",
                self.primary.model,
                self.fallback.model,
                exc.code,
                exc.message[:200],
            )
            return await self.fallback.structured_output(
                schema=schema, system=system, user=user, run_id=run_id, generation=generation,
                role=role, agent_version_id=agent_version_id, artifact_id=artifact_id,
                artifact_type=artifact_type, temperature=temperature, max_tokens=max_tokens,
                repairs=repairs, validate=validate,
            )


def _reasoning_text(message: Any) -> str:
    """Hidden reasoning text from an OpenAI-compatible response, if the model emits it.

    llama.cpp exposes ``reasoning_content`` directly; the OpenAI SDK puts unknown fields
    in ``model_extra``. Only the size is ever used for diagnostics — the text is never
    treated as the answer and never persisted.
    """
    if message is None:
        return ""
    direct = getattr(message, "reasoning_content", None)
    if isinstance(direct, str) and direct:
        return direct
    extra = getattr(message, "model_extra", None)
    if isinstance(extra, dict):
        for key in ("reasoning_content", "reasoning"):
            value = extra.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _empty_completion_condition(*, finish_reason: str, reasoning_chars: int) -> str:
    """A bounded, answer-free description of why a completion had no visible content."""
    reason = finish_reason or "unknown"
    if reasoning_chars > 0:
        return f"reasoning-only completion (finish_reason={reason}, {reasoning_chars} reasoning chars)"
    return f"empty completion (finish_reason={reason})"


def _extract_json(text: str) -> Any:
    """Pull the first JSON object out of a completion, tolerating prose wrappers."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class ProbeResult:
    role_name: str
    reachable: bool
    model: str
    detail: str
    latency_ms: int = 0


# The probe is a liveness check, not a task. Free reasoning routes (e.g. OpenRouter's
# free tier) can spend a small budget on hidden reasoning and return empty content, so
# the probe escalates once to a bounded larger budget. Real task calls are unaffected
# and still fail closed on empty output.
_PROBE_BUDGETS: tuple[int, ...] = (128, 1024)


async def probe(config: ProviderConfig) -> ProbeResult:
    """One tiny real completion to prove the endpoint answers (§46 step 0)."""
    provider = OpenAICompatibleProvider(config)
    last_error = "probe failed"
    for index, budget in enumerate(_PROBE_BUDGETS):
        try:
            result = await provider.chat(
                messages=[{"role": "user", "content": "Reply with the single word: READY"}],
                run_id="PROBE",
                generation=0,
                role="blue_executor" if config.role_name == "BLUE" else "red_attacker",
                max_tokens=budget,
                temperature=0.0,
            )
        except ProviderError as exc:
            last_error = exc.message
            empty = exc.code.endswith("_PROVIDER_EMPTY_RESPONSE")
            if empty and index < len(_PROBE_BUDGETS) - 1:
                continue
            return ProbeResult(role_name=config.role_name, reachable=False, model=config.model, detail=exc.message)
        return ProbeResult(
            role_name=config.role_name,
            reachable=True,
            model=config.model,
            detail=result.text.strip()[:80],
            latency_ms=result.latency_ms,
        )
    return ProbeResult(role_name=config.role_name, reachable=False, model=config.model, detail=last_error)


async def wait_for_endpoints(configs: list[ProviderConfig], attempts: int = 1, delay: float = 2.0) -> list[ProbeResult]:
    results = await asyncio.gather(*(probe(config) for config in configs))
    for _ in range(1, attempts):
        if all(result.reachable for result in results):
            break
        await asyncio.sleep(delay)
        results = await asyncio.gather(*(probe(config) for config in configs))
    return list(results)
