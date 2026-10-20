"""LLMGate — the only entry point to an LLM (CLAUDE.md "Hard Rules — Money & LLM", ADR-0001).

Order of checks for every call:
1. owner-only: a subscription provider serves role=owner only;
2. pause: while `llm_state.paused_until` is in the future, nothing is called;
3. daily cap per kind: a slot is reserved atomically *before* the call;
4. call the provider (no DB transaction is held during the call);
5. on rate limit / auth error: pause with backoff, notify the admin exactly once per
   episode, and tell the caller to retry later. The first successful call ends the episode.

Callers (future procrastinate tasks) handle `LLMDeferred` by rescheduling to `retry_at`.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import LlmState, LlmUsage, Role, User
from app.llm.provider import (
    LLMAuthError,
    LLMInvalidOutput,
    LLMProvider,
    LLMRateLimited,
    LLMRequest,
    LLMResult,
)

log = structlog.get_logger()

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
DeferReason = Literal["paused", "daily_cap", "rate_limited", "auth_error"]


class LLMForbidden(Exception):
    """This user may not use this provider (subscription is owner-only)."""


class LLMDeferred(Exception):
    """Not now — retry at `retry_at`. The work stays queued; nothing is lost."""

    def __init__(self, retry_at: datetime, reason: DeferReason) -> None:
        super().__init__(f"{reason}, retry at {retry_at.isoformat()}")
        self.retry_at = retry_at
        self.reason = reason


class AdminNotifier(Protocol):
    async def notify_admins(self, key: str, **params: str) -> None: ...


class LLMGate:
    def __init__(
        self,
        provider: LLMProvider,
        notifier: AdminNotifier,
        session_factory: SessionFactory,
        settings: Settings | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._provider = provider
        self._notifier = notifier
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._clock = clock
        self._tz = ZoneInfo(self._settings.timezone)

    async def call[T: BaseModel](self, req: LLMRequest[T]) -> LLMResult[T]:
        now = self._clock()
        day = now.astimezone(self._tz).date()

        async with self._session_factory() as db:
            await self._check_allowed(db, req)
            await self._check_not_paused(db, now)
            await self._reserve_slot(db, req, day, now)
            await db.commit()

        try:
            result = await self._provider.complete(req)
        except LLMRateLimited as exc:
            await self._release_slot(req, day)
            raise await self._pause(now, exc.reset_at, "rate_limited") from exc
        except LLMAuthError as exc:
            await self._release_slot(req, day)
            raise await self._pause(now, None, "auth_error") from exc
        except LLMInvalidOutput:
            raise  # the model did run: the slot stays used
        except Exception:
            await self._release_slot(req, day)
            raise

        await self._end_pause_episode()
        log.info(
            "llm_call",
            user_id=str(req.user_id),
            kind=req.kind,
            prompt_version=req.prompt_version,
            provider=result.provider,
            model=result.model,
            duration_ms=result.duration_ms,
            **result.usage,
        )
        return result

    # --- checks -------------------------------------------------------------------------

    async def _check_allowed(self, db: AsyncSession, req: LLMRequest[BaseModel]) -> None:
        if not self._provider.subscription:
            return
        role = await db.scalar(select(User.role).where(User.id == req.user_id))
        if role != Role.OWNER:
            log.warning("llm_forbidden", user_id=str(req.user_id), provider=self._provider.name)
            raise LLMForbidden("the subscription provider serves the owner only")

    async def _check_not_paused(self, db: AsyncSession, now: datetime) -> None:
        paused_until = await db.scalar(
            select(LlmState.paused_until).where(LlmState.provider == self._provider.name)
        )
        if paused_until is not None and paused_until > now:
            raise LLMDeferred(paused_until, "paused")

    async def _reserve_slot(
        self, db: AsyncSession, req: LLMRequest[BaseModel], day: date, now: datetime
    ) -> None:
        cap = self._settings.llm_daily_cap(req.kind)
        reserved = None
        if cap > 0:
            stmt = (
                pg_insert(LlmUsage)
                .values(user_id=req.user_id, kind=req.kind, day=day, count=1)
                .on_conflict_do_update(
                    constraint="uq_llm_usage_user_kind_day",
                    set_={"count": LlmUsage.count + 1},
                    where=LlmUsage.count < cap,
                )
                .returning(LlmUsage.count)
            )
            reserved = (await db.execute(stmt)).scalar_one_or_none()
        if reserved is None:
            await db.rollback()
            raise LLMDeferred(self._next_midnight(now), "daily_cap")

    async def _release_slot(self, req: LLMRequest[BaseModel], day: date) -> None:
        async with self._session_factory() as db:
            await db.execute(
                update(LlmUsage)
                .where(
                    LlmUsage.user_id == req.user_id,
                    LlmUsage.kind == req.kind,
                    LlmUsage.day == day,
                    LlmUsage.count > 0,
                )
                .values(count=LlmUsage.count - 1)
            )
            await db.commit()

    # --- pause episode ------------------------------------------------------------------

    async def _pause(
        self, now: datetime, reset_at: datetime | None, reason: DeferReason
    ) -> LLMDeferred:
        async with self._session_factory() as db:
            await db.execute(
                pg_insert(LlmState)
                .values(provider=self._provider.name, pause_streak=0)
                .on_conflict_do_nothing()
            )
            state = await db.scalar(
                select(LlmState).where(LlmState.provider == self._provider.name).with_for_update()
            )
            assert state is not None
            state.pause_streak += 1
            until = (
                reset_at
                if reset_at is not None and reset_at > now
                else now + self._backoff(state.pause_streak)
            )
            if state.paused_until is None or state.paused_until < until:
                state.paused_until = until
            until = state.paused_until
            notify = state.notified_at is None
            if notify:
                state.notified_at = now
            await db.commit()

        log.warning("llm_paused", reason=reason, until=until.isoformat(), notify=notify)
        if notify:
            key = "llm_rate_limited" if reason == "rate_limited" else "llm_auth_error"
            local = until.astimezone(self._tz)
            try:
                await self._notifier.notify_admins(key, until=local.strftime("%d.%m %H:%M"))
            except Exception:
                # The pause itself is in place; a lost message must not break the caller.
                log.exception("llm_pause_notify_failed")
        return LLMDeferred(until, reason)

    async def _end_pause_episode(self) -> None:
        async with self._session_factory() as db:
            await db.execute(
                update(LlmState)
                .where(
                    LlmState.provider == self._provider.name,
                    (LlmState.pause_streak > 0) | LlmState.notified_at.is_not(None),
                )
                .values(pause_streak=0, notified_at=None, paused_until=None)
            )
            await db.commit()

    def _backoff(self, streak: int) -> timedelta:
        """60 → 120 → 240 → 300 (max) minutes with the default settings."""
        minutes = self._settings.llm_pause_default_minutes * 2 ** (streak - 1)
        return timedelta(minutes=min(minutes, self._settings.llm_pause_max_minutes))

    def _next_midnight(self, now: datetime) -> datetime:
        local = now.astimezone(self._tz)
        tomorrow = local.date() + timedelta(days=1)
        midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=self._tz)
        return midnight.astimezone(UTC)


_gate: LLMGate | None = None


def get_gate() -> LLMGate:
    """Process-wide gate built from settings (one provider instance → one call at a time)."""
    global _gate
    if _gate is None:
        from app.bot.notifier import TelegramAdminNotifier
        from app.db.session import get_sessionmaker
        from app.llm.claude_code import ClaudeCodeSubscriptionProvider
        from app.llm.fake import FakeProvider

        settings = get_settings()
        provider: LLMProvider = (
            ClaudeCodeSubscriptionProvider(settings)
            if settings.llm_provider == "claude_code"
            else FakeProvider()
        )
        sessionmaker = get_sessionmaker()
        _gate = LLMGate(provider, TelegramAdminNotifier(sessionmaker, settings), sessionmaker)
    return _gate
