"""LLM provider backed by Claude Code on the owner's Claude Pro subscription (ADR-0001).

Runs `claude -p --output-format json --json-schema ...` as a subprocess:

* env comes from `sanitized_env()` — ANTHROPIC_API_KEY is never passed, so the call
  cannot silently switch to pay-as-you-go billing. `--bare` is never used: it
  authenticates with an API key only.
* cwd is a fresh empty temp dir, so no CLAUDE.md / project settings are picked up.
* the prompt (may contain CV text) goes through stdin, never argv — it stays out of `ps`.
* no tools, no MCP servers, no settings files, no session persistence.
* one call at a time per provider instance — gentle on the subscription limits.
"""

import asyncio
import json
import re
import tempfile
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.env_guard import sanitized_env
from app.llm.provider import (
    LLMAuthError,
    LLMInvalidOutput,
    LLMRateLimited,
    LLMRequest,
    LLMResult,
    LLMUnavailable,
)

log = structlog.get_logger()

_RATE_LIMIT_RE = re.compile(
    r"usage limit|rate limit|limit reached|hit your limit|(5-hour|weekly|session) limit",
    re.IGNORECASE,
)
_AUTH_RE = re.compile(
    r"not logged in|please run /login|invalid api key|oauth token|authentication|unauthori[sz]ed",
    re.IGNORECASE,
)
# "Claude AI usage limit reached|1760961600"
_RESET_EPOCH_RE = re.compile(r"\|(\d{10})\b")
# "... resets 3pm (Europe/Berlin)", "resets at 15:30"
_RESET_TIME_RE = re.compile(
    r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s*\(([^)]+)\))?",
    re.IGNORECASE,
)


def parse_reset_at(text: str, now: datetime | None = None) -> datetime | None:
    """Best effort: when does the limit reset? None if the message does not say."""
    now = now or datetime.now(UTC)
    if m := _RESET_EPOCH_RE.search(text):
        return datetime.fromtimestamp(int(m.group(1)), UTC)
    if m := _RESET_TIME_RE.search(text):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        meridiem = (m.group(3) or "").lower()
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        try:
            tz = ZoneInfo(m.group(4)) if m.group(4) else None
        except (ZoneInfoNotFoundError, ValueError):
            tz = None
        local_now = now.astimezone(tz)  # tz=None → the machine's local zone
        reset = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if reset <= local_now:
            reset += timedelta(days=1)
        return reset.astimezone(UTC)
    return None


def _classify_failure(text: str, status: int | None) -> Exception:
    if status == 429 or _RATE_LIMIT_RE.search(text):
        return LLMRateLimited(parse_reset_at(text), message=text[:300])
    if status in (401, 403) or _AUTH_RE.search(text):
        return LLMAuthError(text[:300])
    return LLMUnavailable(text[:300] or "claude failed without output")


def _main_model(envelope: dict[str, Any]) -> str | None:
    """`modelUsage` may also list a small helper model; the main one wrote the most tokens."""
    usage = envelope.get("modelUsage")
    if not isinstance(usage, dict) or not usage:
        return None
    return str(max(usage, key=lambda name: usage[name].get("outputTokens", 0)))


def _token_usage(envelope: dict[str, Any]) -> dict[str, int]:
    usage = envelope.get("usage") or {}
    keys = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    return {k: int(usage[k]) for k in keys if isinstance(usage.get(k), int)}


class ClaudeCodeSubscriptionProvider:
    name = "claude_code"
    subscription = True

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._lock = asyncio.Semaphore(1)

    async def complete[T: BaseModel](self, req: LLMRequest[T]) -> LLMResult[T]:
        async with self._lock:
            for attempt in (1, 2):
                started = time.monotonic()
                envelope = await self._run(req)
                try:
                    data = self._parse_output(req, envelope)
                except LLMInvalidOutput:
                    if attempt == 2:
                        raise
                    log.warning("llm_invalid_output_retry", kind=req.kind, user_id=str(req.user_id))
                    continue
                return LLMResult(
                    data=data,
                    provider=self.name,
                    model=_main_model(envelope),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    usage=_token_usage(envelope),
                )
        raise AssertionError("unreachable")

    def _command(self, req: LLMRequest[Any]) -> list[str]:
        return [
            self._settings.claude_bin,
            "-p",
            "--output-format",
            "json",
            "--model",
            self._settings.llm_model(req.kind),
            "--tools",
            "",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--system-prompt",
            req.system,
            "--json-schema",
            json.dumps(req.json_schema()),
        ]

    async def _run(self, req: LLMRequest[Any]) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="ws-llm-") as cwd:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *self._command(req),
                    cwd=cwd,
                    env=sanitized_env(),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise LLMAuthError(f"claude binary not found: {self._settings.claude_bin}") from exc
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(req.prompt.encode()),
                    timeout=self._settings.llm_timeout_seconds,
                )
            except TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise LLMUnavailable("claude timed out") from exc

        out, err = stdout.decode(errors="replace"), stderr.decode(errors="replace")
        try:
            envelope = json.loads(out)
        except json.JSONDecodeError:
            raise _classify_failure(f"{out}\n{err}".strip(), None) from None
        if not isinstance(envelope, dict):
            raise LLMUnavailable("unexpected claude output")

        if envelope.get("is_error") or proc.returncode != 0:
            status = envelope.get("api_error_status")
            text = str(envelope.get("result") or err or envelope.get("subtype") or "")
            raise _classify_failure(text, status if isinstance(status, int) else None)
        return envelope

    @staticmethod
    def _parse_output[T: BaseModel](req: LLMRequest[T], envelope: dict[str, Any]) -> T:
        payload = envelope.get("structured_output")
        if payload is None:
            # Fallback: the model may have put the JSON into the plain text result.
            try:
                payload = json.loads(str(envelope.get("result") or ""))
            except json.JSONDecodeError as exc:
                raise LLMInvalidOutput("no structured output") from exc
        try:
            return req.output.model_validate(payload)
        except ValidationError as exc:
            raise LLMInvalidOutput(str(exc)) from exc
