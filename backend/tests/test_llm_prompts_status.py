import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.llm.fake import FakeProvider
from app.llm.gate import LLMGate, get_gate
from app.llm.prompts import healthcheck
from app.llm.provider import LLMKind
from app.main import app
from tests.conftest import register


def test_prompt_build() -> None:
    user_id = uuid.uuid4()
    req = healthcheck.PROMPT.build(user_id=user_id, word="abc")
    assert req.kind == LLMKind.CHECK
    assert req.user_id == user_id
    assert req.prompt.endswith("abc")
    assert req.prompt_version == "healthcheck@v1"
    assert req.json_schema()["required"] == ["ok", "echo"]


def test_prompt_missing_param_is_an_error() -> None:
    with pytest.raises(KeyError):
        healthcheck.PROMPT.build(user_id=uuid.uuid4())


@pytest.fixture
def provider(db: AsyncSession) -> Iterator[FakeProvider]:
    fake = FakeProvider()

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db

    class NoNotifier:
        async def notify_admins(self, key: str, **params: str) -> None:
            pass

    gate = LLMGate(fake, NoNotifier(), factory, Settings())
    app.dependency_overrides[get_gate] = lambda: gate
    yield fake
    app.dependency_overrides.pop(get_gate, None)


async def test_status_for_owner(client: AsyncClient, provider: FakeProvider) -> None:
    user = await register(client, email="owner@example.com")
    provider.queue({"ok": True, "echo": "x"})
    gate = app.dependency_overrides[get_gate]()
    await gate.call(healthcheck.PROMPT.build(user_id=uuid.UUID(str(user["id"])), word="x"))

    data = (await client.get("/llm/status")).json()
    assert data["provider"] == "fake"
    assert data["available"] is True
    assert data["paused_until"] is None
    usage = {u["kind"]: (u["used"], u["cap"]) for u in data["usage"]}
    assert usage == {"parse": (0, 5), "score": (0, 30), "draft": (0, 8), "check": (1, 3)}


async def test_status_subscription_not_available_for_other_users(
    client: AsyncClient, provider: FakeProvider
) -> None:
    await register(client)
    assert (await client.get("/llm/status")).json()["available"] is False


async def test_status_requires_login(client: AsyncClient, provider: FakeProvider) -> None:
    assert (await client.get("/llm/status")).status_code == 401
