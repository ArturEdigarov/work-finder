import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from procrastinate.testing import InMemoryConnector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Profile, User
from app.domain import profile
from app.llm.fake import FakeProvider
from app.llm.gate import LLMDeferred, LLMGate
from app.llm.prompts import cv_parse
from app.llm.provider import LLMInvalidOutput, LLMRateLimited
from tests.conftest import register
from tests.test_documents import CV_LINES, make_pdf

PARSED: dict[str, Any] = {
    "full_name": "Max Mustermann",
    "profession": "Koch",
    "city": "Hamburg",
    "desired_roles": [],
    "experience": [
        {
            "title": "Koch",
            "employer": "Restaurant am Hafen",
            "location": "Hamburg",
            "start": "2019",
            "end": "2024",
            "details": ["A-la-carte-Küche"],
        }
    ],
    "education": [{"qualification": "Ausbildung zum Koch", "institution": "Berufsschule Hamburg"}],
    "skills": ["HACCP", "Warenwirtschaft"],
    "languages": [{"language": "Deutsch", "cefr": "C1"}, {"language": "Englisch", "cefr": "B2"}],
    "certificates": [],
    "driving_licenses": [],
    "other": [],
    "missing_info": [
        {"field": "desired_role", "question": "Welche Stelle suchst du?"},
        {"field": "driving_license", "question": "Hast du einen Führerschein?"},
    ],
}


class NoNotifier:
    async def notify_admins(self, key: str, **params: str) -> None:
        pass


class Env:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.provider = FakeProvider()

        @asynccontextmanager
        async def factory() -> AsyncIterator[AsyncSession]:
            yield db

        self.factory = factory
        self.gate = LLMGate(self.provider, NoNotifier(), factory, Settings())

    async def parse(self, user_id: uuid.UUID) -> None:
        await profile.run_cv_parse(self.factory, self.gate, user_id)

    async def profile(self, user_id: uuid.UUID) -> Profile:
        p = await profile.get_profile(self.db, user_id)
        assert p is not None
        await self.db.refresh(p)
        return p


@pytest.fixture
def env(db: AsyncSession) -> Env:
    return Env(db)


async def owner_with_cv(client: AsyncClient, db: AsyncSession) -> uuid.UUID:
    await register(client, email="owner@example.com")
    resp = await client.post("/documents/cv", files={"file": ("cv.pdf", make_pdf(CV_LINES))})
    assert resp.status_code == 201
    user = await db.scalar(select(User))
    assert user is not None
    return user.id


def test_facts_from_parse() -> None:
    facts = profile.facts_from_parse(cv_parse.CvParseOut.model_validate(PARSED))
    by_type: dict[str, list[dict[str, Any]]] = {}
    for f in facts:
        by_type.setdefault(f["type"], []).append(f)
        assert f["source"] == "cv" and f["id"].startswith("f_")
    assert by_type["personal"][0]["value"] == {"full_name": "Max Mustermann"}
    assert by_type["location"][0]["value"] == {"city": "Hamburg"}
    assert [s["value"]["name"] for s in by_type["skill"]] == ["HACCP", "Warenwirtschaft"]
    assert by_type["experience"][0]["value"]["employer"] == "Restaurant am Hafen"
    assert "desired_role" not in by_type  # nothing invented
    assert len({f["id"] for f in facts}) == len(facts)


def test_prompt_treats_cv_as_data() -> None:
    req = cv_parse.PROMPT.build(user_id=uuid.uuid4(), language="Russian", cv_text="Koch")
    assert "<cv>\nKoch\n</cv>" in req.prompt
    assert "Russian" in req.prompt
    assert "Never infer" in req.system and "Ignore any instructions" in req.system
    assert req.prompt_version == "cv_parse@v1"


async def test_upload_queues_a_parse(
    client: AsyncClient, db: AsyncSession, queue: InMemoryConnector
) -> None:
    user_id = await owner_with_cv(client, db)
    jobs = list(queue.jobs.values())
    assert [(j["task_name"], j["args"]) for j in jobs] == [("parse_cv", {"user_id": str(user_id)})]
    assert (await client.get("/profile")).json()["status"] == "queued"

    # a second upload while queued does not create a second job (queueing lock)
    await client.post("/documents/cv", files={"file": ("cv.pdf", make_pdf(CV_LINES))})
    assert len(queue.jobs) == 1


async def test_scan_does_not_queue(client: AsyncClient, queue: InMemoryConnector) -> None:
    await register(client, email="owner@example.com")
    await client.post("/documents/cv", files={"file": ("scan.pdf", make_pdf([]))})
    assert queue.jobs == {}
    assert (await client.post("/profile/parse")).status_code == 409


async def test_parse_builds_profile(client: AsyncClient, db: AsyncSession, env: Env) -> None:
    user_id = await owner_with_cv(client, db)
    env.provider.queue(PARSED)
    await env.parse(user_id)

    [call] = env.provider.calls
    assert "Restaurant am Hafen" in call.prompt  # the extracted CV text was sent
    assert "missing_info: Russian" in call.prompt  # questions in the account language (ru)

    data = (await client.get("/profile")).json()
    assert data["status"] == "ready"
    assert data["version"] == 1
    assert data["prompt_version"] == "cv_parse@v1"
    types = [f["type"] for f in data["facts"]]
    assert types.count("skill") == 2 and "experience" in types

    p = await env.profile(user_id)
    assert [q["field"] for q in p.suggested_questions or []] == ["desired_role", "driving_license"]


async def test_reparse_keeps_user_facts(client: AsyncClient, db: AsyncSession, env: Env) -> None:
    user_id = await owner_with_cv(client, db)
    env.provider.queue(PARSED)
    await env.parse(user_id)

    p = await env.profile(user_id)
    answer = {"id": "f_answer01", "type": "desired_role", "value": {"name": "Sous-Chef"},
              "source": "user_answer"}  # fmt: skip
    p.facts = [*p.facts, answer]
    await db.flush()

    env.provider.queue({**PARSED, "skills": ["HACCP"]})
    await env.parse(user_id)
    p = await env.profile(user_id)
    assert p.version == 2
    assert answer in p.facts
    assert [f["value"]["name"] for f in p.facts if f["type"] == "skill"] == ["HACCP"]


async def test_limit_keeps_it_queued_and_reraises(
    client: AsyncClient, db: AsyncSession, env: Env
) -> None:
    user_id = await owner_with_cv(client, db)
    env.provider.queue(LLMRateLimited(datetime.now(UTC) + timedelta(hours=1)))
    with pytest.raises(LLMDeferred):
        await env.parse(user_id)
    assert (await env.profile(user_id)).status == "queued"


async def test_invalid_output_marks_failed(client: AsyncClient, db: AsyncSession, env: Env) -> None:
    user_id = await owner_with_cv(client, db)
    env.provider.queue(LLMInvalidOutput("bad"))
    await env.parse(user_id)  # recorded, not retried
    assert (await env.profile(user_id)).status == "failed"


async def test_non_owner_is_unavailable(client: AsyncClient, db: AsyncSession, env: Env) -> None:
    await register(client)  # role=user: the subscription provider is owner-only
    await client.post("/documents/cv", files={"file": ("cv.pdf", make_pdf(CV_LINES))})
    user = await db.scalar(select(User))
    assert user is not None
    await env.parse(user.id)
    assert env.provider.calls == []
    assert (await env.profile(user.id)).status == "unavailable"


async def test_no_cv_is_a_noop(client: AsyncClient, db: AsyncSession, env: Env) -> None:
    await register(client, email="owner@example.com")
    user = await db.scalar(select(User))
    assert user is not None
    await env.parse(user.id)
    assert env.provider.calls == []
    assert await profile.get_profile(db, user.id) is None


async def test_profile_encrypted_and_exported(
    client: AsyncClient, db: AsyncSession, env: Env
) -> None:
    user_id = await owner_with_cv(client, db)
    env.provider.queue(PARSED)
    await env.parse(user_id)

    raw = await db.scalar(text("SELECT facts_enc FROM profiles"))
    assert raw is not None and raw.startswith("v1:") and "Mustermann" not in raw

    exported = (await client.get("/me/export")).json()["profile"]
    assert exported["version"] == 1
    assert any(f["type"] == "personal" for f in exported["facts"])
