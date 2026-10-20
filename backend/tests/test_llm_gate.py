import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import LlmState, LlmUsage, Role, User
from app.llm.fake import FakeProvider
from app.llm.gate import LLMDeferred, LLMForbidden, LLMGate
from app.llm.provider import (
    LLMAuthError,
    LLMInvalidOutput,
    LLMKind,
    LLMRateLimited,
    LLMRequest,
    LLMUnavailable,
)

Berlin = ZoneInfo("Europe/Berlin")
OK = {"value": "ok"}


class Out(BaseModel):
    value: str


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 20, 10, 0, tzinfo=Berlin).astimezone(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class RecordingNotifier:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, dict[str, str]]] = []
        self.fail = fail

    async def notify_admins(self, key: str, **params: str) -> None:
        self.sent.append((key, params))
        if self.fail:
            raise RuntimeError("telegram down")


class Env:
    def __init__(self, db: AsyncSession, **settings: Any) -> None:
        self.db = db
        self.provider = FakeProvider()
        self.notifier = RecordingNotifier()
        self.clock = Clock()

        @asynccontextmanager
        async def session_factory() -> AsyncIterator[AsyncSession]:
            yield db  # the test transaction; commit() only releases a savepoint

        self.gate = LLMGate(
            self.provider, self.notifier, session_factory, Settings(**settings), self.clock
        )

    async def user(self, role: Role = Role.OWNER) -> uuid.UUID:
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            email_hash=uuid.uuid4().hex,
            password_hash="x",
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        return user.id

    async def call(self, user_id: uuid.UUID, kind: LLMKind = LLMKind.SCORE) -> Out:
        req = LLMRequest(kind=kind, user_id=user_id, system="s", prompt="p", output=Out)
        return (await self.gate.call(req)).data

    async def usage(self, user_id: uuid.UUID, kind: LLMKind = LLMKind.SCORE) -> int:
        count = await self.db.scalar(
            select(LlmUsage.count).where(LlmUsage.user_id == user_id, LlmUsage.kind == kind)
        )
        return count or 0

    async def state(self) -> LlmState | None:
        state = await self.db.scalar(select(LlmState))
        if state is not None:
            await self.db.refresh(state)
        return state


@pytest.fixture
def env(db: AsyncSession) -> Env:
    return Env(db)


async def test_owner_call_is_counted(env: Env) -> None:
    owner = await env.user()
    env.provider.queue(OK)
    assert await env.call(owner) == Out(value="ok")
    assert await env.usage(owner) == 1


async def test_subscription_is_owner_only(env: Env) -> None:
    user = await env.user(Role.USER)
    with pytest.raises(LLMForbidden):
        await env.call(user)
    assert env.provider.calls == []
    assert await env.usage(user) == 0


async def test_admin_role_is_not_owner(env: Env) -> None:
    admin = await env.user(Role.ADMIN)
    with pytest.raises(LLMForbidden):
        await env.call(admin)


async def test_api_provider_serves_any_user(env: Env) -> None:
    env.provider.subscription = False
    user = await env.user(Role.USER)
    env.provider.queue(OK)
    assert await env.call(user) == Out(value="ok")


async def test_daily_cap_defers_until_berlin_midnight(db: AsyncSession) -> None:
    env = Env(db, llm_daily_cap_score=2)
    owner = await env.user()
    env.provider.queue(OK, OK, OK)
    await env.call(owner)
    await env.call(owner)

    with pytest.raises(LLMDeferred) as exc:
        await env.call(owner)
    assert exc.value.reason == "daily_cap"
    assert exc.value.retry_at == datetime(2026, 10, 21, tzinfo=Berlin)
    assert len(env.provider.calls) == 2
    assert await env.usage(owner) == 2

    # caps are per kind
    env.provider.queue(OK)
    await env.call(owner, LLMKind.DRAFT)

    # and per day
    env.clock.advance(hours=14)  # 00:00 Berlin next day
    await env.call(owner)
    assert len(env.provider.calls) == 4


async def test_zero_cap_disables_kind(db: AsyncSession) -> None:
    env = Env(db, llm_daily_cap_parse=0)
    owner = await env.user()
    with pytest.raises(LLMDeferred, match="daily_cap"):
        await env.call(owner, LLMKind.PARSE)
    assert env.provider.calls == []


async def test_rate_limit_pauses_and_notifies_once(env: Env) -> None:
    owner = await env.user()
    reset_at = env.clock.now + timedelta(hours=3)
    env.provider.queue(LLMRateLimited(reset_at))

    with pytest.raises(LLMDeferred) as exc:
        await env.call(owner)
    assert exc.value.reason == "rate_limited"
    assert exc.value.retry_at == reset_at
    assert env.notifier.sent == [("llm_rate_limited", {"until": "20.10 13:00"})]
    assert await env.usage(owner) == 0  # the slot is released

    # while paused nothing reaches the provider and no new message is sent
    with pytest.raises(LLMDeferred, match="paused"):
        await env.call(owner)
    assert len(env.provider.calls) == 1
    assert len(env.notifier.sent) == 1


async def test_backoff_without_reset_time_and_single_message_per_episode(env: Env) -> None:
    owner = await env.user()
    pauses = []
    for _ in range(4):
        env.provider.queue(LLMRateLimited())
        with pytest.raises(LLMDeferred) as exc:
            await env.call(owner)
        pauses.append(exc.value.retry_at - env.clock.now)
        env.clock.now = exc.value.retry_at  # the pause has passed, the limit is still there
    assert pauses == [timedelta(minutes=m) for m in (60, 120, 240, 300)]
    assert len(env.notifier.sent) == 1

    # a successful call ends the episode
    env.provider.queue(OK)
    await env.call(owner)
    state = await env.state()
    assert state is not None
    assert (state.pause_streak, state.notified_at, state.paused_until) == (0, None, None)

    # the next limit is a new episode: backoff restarts, one new message
    env.provider.queue(LLMRateLimited())
    with pytest.raises(LLMDeferred) as exc:
        await env.call(owner)
    assert exc.value.retry_at - env.clock.now == timedelta(minutes=60)
    assert len(env.notifier.sent) == 2


async def test_auth_error_pauses_with_its_own_message(env: Env) -> None:
    owner = await env.user()
    env.provider.queue(LLMAuthError("Not logged in"))
    with pytest.raises(LLMDeferred) as exc:
        await env.call(owner)
    assert exc.value.reason == "auth_error"
    assert [key for key, _ in env.notifier.sent] == ["llm_auth_error"]
    assert await env.usage(owner) == 0


async def test_invalid_output_keeps_the_slot(env: Env) -> None:
    owner = await env.user()
    env.provider.queue(LLMInvalidOutput("bad"))
    with pytest.raises(LLMInvalidOutput):
        await env.call(owner)
    assert await env.usage(owner) == 1  # tokens were spent


async def test_transient_error_releases_the_slot(env: Env) -> None:
    owner = await env.user()
    env.provider.queue(LLMUnavailable("timeout"))
    with pytest.raises(LLMUnavailable):
        await env.call(owner)
    assert await env.usage(owner) == 0
    assert await env.state() is None  # no pause for transient errors


async def test_notifier_failure_does_not_lose_the_pause(env: Env) -> None:
    env.notifier.fail = True
    owner = await env.user()
    env.provider.queue(LLMRateLimited())
    with pytest.raises(LLMDeferred, match="rate_limited"):
        await env.call(owner)
    state = await env.state()
    assert state is not None and state.paused_until is not None
