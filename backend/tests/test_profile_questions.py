from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import main as bot_main
from app.bot import notifier as notifier_module
from app.core.config import Settings
from app.db.models import Profile, User
from app.domain import profile
from tests.conftest import register
from tests.test_profile import PARSED, Env, owner_with_cv

# --- domain -----------------------------------------------------------------------------


def test_merge_keeps_history_and_skips_handled_fields() -> None:
    existing = [
        {
            "id": "q_1",
            "field": "desired_role",
            "question": "?",
            "status": "answered",
            "fact_ids": [],
        },
        {"id": "q_2", "field": "availability", "question": "?", "status": "open", "fact_ids": []},
        {
            "id": "q_3",
            "field": "relocation",
            "question": "?",
            "status": "dismissed",
            "fact_ids": [],
        },
    ]
    suggested = [
        {"field": "desired_role", "question": "again?"},  # already answered
        {"field": "relocation", "question": "again?"},  # dismissed: not asked again
        {"field": "availability", "question": "Ab wann?"},
    ]
    merged = profile.merge_questions(existing, suggested)
    assert [(q["field"], q["status"]) for q in merged] == [
        ("desired_role", "answered"),
        ("relocation", "dismissed"),
        ("availability", "open"),
    ]
    assert merged[2]["question"] == "Ab wann?" and merged[2]["id"] != "q_2"


def test_legacy_questions_get_stable_ids() -> None:
    p = Profile(questions=[{"field": "desired_role", "question": "Welche Stelle?"}])
    first, second = profile.questions_of(p), profile.questions_of(p)
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["status"] == "open"


# --- API --------------------------------------------------------------------------------


async def ready_profile(client: AsyncClient, db: AsyncSession) -> dict[str, Any]:
    env = Env(db)
    user_id = await owner_with_cv(client, db)
    env.provider.queue(PARSED)
    await env.parse(user_id)
    data: dict[str, Any] = (await client.get("/profile")).json()
    return data


async def test_answer_desired_role_creates_role_facts(
    client: AsyncClient, db: AsyncSession
) -> None:
    data = await ready_profile(client, db)
    q = next(q for q in data["questions"] if q["field"] == "desired_role")

    resp = await client.post(
        f"/profile/questions/{q['id']}/answer", json={"text": "Sous-Chef, Küchenchef"}
    )
    assert resp.status_code == 200
    data = resp.json()
    roles = [f for f in data["facts"] if f["type"] == "desired_role"]
    assert [r["value"]["name"] for r in roles] == ["Sous-Chef", "Küchenchef"]
    assert all(r["source"] == "user_answer" for r in roles)
    assert next(x for x in data["questions"] if x["id"] == q["id"])["status"] == "answered"

    again = await client.post(f"/profile/questions/{q['id']}/answer", json={"text": "x"})
    assert (again.status_code, again.json()["detail"]) == (422, "question_closed")


async def test_answer_other_field_creates_answer_fact(
    client: AsyncClient, db: AsyncSession
) -> None:
    data = await ready_profile(client, db)
    q = next(q for q in data["questions"] if q["field"] == "driving_license")
    data = (
        await client.post(f"/profile/questions/{q['id']}/answer", json={"text": "Ja, B"})
    ).json()
    [fact] = [f for f in data["facts"] if f["type"] == "answer"]
    assert fact["value"] == {"field": "driving_license", "question": q["question"], "text": "Ja, B"}


async def test_answers_survive_reparse(client: AsyncClient, db: AsyncSession) -> None:
    data = await ready_profile(client, db)
    q = next(q for q in data["questions"] if q["field"] == "desired_role")
    await client.post(f"/profile/questions/{q['id']}/answer", json={"text": "Sous-Chef"})

    env = Env(db)
    user = await db.scalar(select(User))
    assert user is not None
    env.provider.queue(PARSED)  # Claude suggests desired_role again
    await env.parse(user.id)

    data = (await client.get("/profile")).json()
    assert [f["value"]["name"] for f in data["facts"] if f["type"] == "desired_role"] == [
        "Sous-Chef"
    ]
    open_fields = [q["field"] for q in data["questions"] if q["status"] == "open"]
    assert "desired_role" not in open_fields


async def test_dismiss_and_errors(client: AsyncClient, db: AsyncSession) -> None:
    data = await ready_profile(client, db)
    q = data["questions"][0]
    data = (await client.post(f"/profile/questions/{q['id']}/dismiss")).json()
    assert data["questions"][0]["status"] == "dismissed"

    assert (await client.post("/profile/questions/q_nope/dismiss")).status_code == 404
    empty = await client.post(
        f"/profile/questions/{data['questions'][1]['id']}/answer", json={"text": " "}
    )
    assert (empty.status_code, empty.json()["detail"]) == (422, "empty_answer")


async def test_fact_editing(client: AsyncClient, db: AsyncSession) -> None:
    data = await ready_profile(client, db)
    skill = next(f for f in data["facts"] if f["type"] == "skill")

    data = (
        await client.patch(
            f"/profile/facts/{skill['id']}", json={"value": {"name": "HACCP-Schulung"}}
        )
    ).json()
    edited = next(f for f in data["facts"] if f["id"] == skill["id"])  # id is stable
    assert (edited["value"], edited["source"]) == ({"name": "HACCP-Schulung"}, "user_edit")

    data = (
        await client.post("/profile/facts", json={"type": "skill", "value": {"name": "Sushi"}})
    ).json()
    assert any(
        f["value"] == {"name": "Sushi"} and f["source"] == "user_edit" for f in data["facts"]
    )

    before = len(data["facts"])
    data = (await client.delete(f"/profile/facts/{skill['id']}")).json()
    assert len(data["facts"]) == before - 1

    assert (await client.delete("/profile/facts/f_missing")).status_code == 404
    bad = await client.post("/profile/facts", json={"type": "hobby", "value": {"x": "y"}})
    assert bad.status_code == 422
    empty = await client.post("/profile/facts", json={"type": "skill", "value": {"name": "  "}})
    assert empty.json()["detail"] == "empty_fact"


async def test_no_profile_yet(client: AsyncClient) -> None:
    await register(client)
    assert (
        await client.post("/profile/facts", json={"type": "skill", "value": {"name": "x"}})
    ).status_code == 404


# --- bot --------------------------------------------------------------------------------


class Sent:
    messages: ClassVar[list[tuple[int, str, Any]]] = []


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeMessage:
    def __init__(self, chat_id: int, text: str) -> None:
        self.chat = FakeChat(chat_id)
        self.text = text
        self.from_user = None
        self.markup_cleared = False

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        Sent.messages.append((self.chat.id, text, reply_markup))

    async def edit_reply_markup(self, reply_markup: Any = None) -> None:
        self.markup_cleared = True


class FakeCallback:
    def __init__(self, message: FakeMessage, data: str) -> None:
        self.message = message
        self.data = data
        self.answered: str | None = None

    async def answer(self, text: str | None = None) -> None:
        self.answered = text


@pytest.fixture
def bot_db(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(bot_main, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(bot_main, "Message", FakeMessage)  # isinstance check in on_skip
    Sent.messages = []
    return db


async def link_chat(db: AsyncSession, chat_id: int = 555) -> User:
    user = await db.scalar(select(User))
    assert user is not None
    user.telegram_chat_id = chat_id
    await db.flush()
    return user


async def test_bot_answers_questions_one_by_one(client: AsyncClient, bot_db: AsyncSession) -> None:
    await ready_profile(client, bot_db)
    await link_chat(bot_db)

    await bot_main.on_questions(FakeMessage(555, "/questions"))  # type: ignore[arg-type]
    intro, first = Sent.messages[-2], Sent.messages[-1]
    assert "2" in intro[1]
    assert first[1] == "❓ Welche Stelle suchst du?" and first[2] is not None  # skip button

    await bot_main.on_text(FakeMessage(555, "Sous-Chef"))  # type: ignore[arg-type]
    assert Sent.messages[-2][1] == "Сохранил ✅"
    assert Sent.messages[-1][1] == "❓ Hast du einen Führerschein?"

    data = (await client.get("/profile")).json()
    assert [f["value"]["name"] for f in data["facts"] if f["type"] == "desired_role"] == [
        "Sous-Chef"
    ]

    # skip the second question with the inline button
    q2 = next(q for q in data["questions"] if q["status"] == "open")
    msg = FakeMessage(555, "")
    callback = FakeCallback(msg, f"q_skip:{q2['id']}")
    await bot_main.on_skip(callback)  # type: ignore[arg-type]
    assert callback.answered == "Пропущено." and msg.markup_cleared
    assert Sent.messages[-1][1].startswith("Вопросов больше нет")


async def test_bot_unlinked_chat(bot_db: AsyncSession) -> None:
    await bot_main.on_text(FakeMessage(999, "hallo"))  # type: ignore[arg-type]
    assert "не привязан" in Sent.messages[-1][1] or "isn't linked" in Sent.messages[-1][1]


async def test_profile_ready_notification(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ready_profile(client, db)
    await link_chat(db, 777)

    sent: list[tuple[int, str]] = []

    class FakeBot:
        def __init__(self, token: str) -> None:
            self.session = self

        async def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> None:
            sent.append((chat_id, text))

        async def close(self) -> None:
            pass

    monkeypatch.setattr(notifier_module, "Bot", FakeBot)

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db

    user = await db.scalar(select(User))
    assert user is not None
    await notifier_module.notify_profile_ready(
        factory, user.id, Settings(telegram_bot_token=SecretStr("1:x"))
    )
    assert [chat for chat, _ in sent] == [777, 777, 777]
    assert sent[0][1].startswith("✅ Профиль готов:")
    assert sent[2][1] == "❓ Welche Stelle suchst du?"
