import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import LlmUsage, User
from app.llm.fake import FakeProvider
from app.llm.provider import LLMInvalidOutput, LLMKind, LLMRateLimited, LLMRequest
from tests.conftest import PASSWORD, register


class Answer(BaseModel):
    chance_pct: int
    reason: str


def request(kind: LLMKind = LLMKind.SCORE) -> LLMRequest[Answer]:
    return LLMRequest(kind=kind, user_id=uuid.uuid4(), system="sys", prompt="hello", output=Answer)


async def test_fake_returns_validated_model() -> None:
    provider = FakeProvider([{"chance_pct": 70, "reason": "fits"}])
    result = await provider.complete(request())
    assert result.data == Answer(chance_pct=70, reason="fits")
    assert provider.calls[0].prompt == "hello"


async def test_fake_invalid_output() -> None:
    provider = FakeProvider([{"chance_pct": "a lot"}])
    with pytest.raises(LLMInvalidOutput):
        await provider.complete(request())


async def test_fake_raises_queued_error() -> None:
    provider = FakeProvider([LLMRateLimited()])
    with pytest.raises(LLMRateLimited):
        await provider.complete(request())


def test_request_exposes_json_schema() -> None:
    schema = request().json_schema()
    assert schema["required"] == ["chance_pct", "reason"]


def test_per_kind_settings() -> None:
    settings = get_settings()
    assert [settings.llm_daily_cap(k) for k in LLMKind] == [5, 30, 8, 3]
    assert {settings.llm_model(k) for k in LLMKind} == {"sonnet"}


async def test_usage_is_exported_and_deleted_with_user(
    client: AsyncClient, db: AsyncSession
) -> None:
    await register(client)
    user = await db.scalar(select(User))
    assert user is not None
    db.add(LlmUsage(user_id=user.id, kind=LLMKind.SCORE, day=date(2026, 10, 20), count=3))
    await db.flush()

    export = (await client.get("/me/export")).json()
    assert export["llm_usage"] == [{"day": "2026-10-20", "kind": "score", "count": 3}]

    await client.post("/me/delete", json={"password": PASSWORD})
    assert await db.scalar(select(func.count()).select_from(LlmUsage)) == 0
