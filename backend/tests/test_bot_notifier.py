import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notifier as notifier_module
from app.bot.notifier import TelegramAdminNotifier
from app.core.config import Settings
from app.db.models import Role, User


class FakeBot:
    sent: ClassVar[list[tuple[int, str]]] = []

    def __init__(self, token: str) -> None:
        self.session = self

    async def send_message(self, chat_id: int, text: str) -> None:
        FakeBot.sent.append((chat_id, text))

    async def close(self) -> None:
        pass


def make_notifier(db: AsyncSession, **settings: Any) -> TelegramAdminNotifier:
    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db

    return TelegramAdminNotifier(factory, Settings(**settings))


async def add_user(db: AsyncSession, role: Role, chat_id: int | None, locale: str) -> None:
    db.add(
        User(
            email=f"{uuid.uuid4()}@example.com",
            email_hash=uuid.uuid4().hex,
            password_hash="x",
            role=role,
            locale=locale,
            telegram_chat_id=chat_id,
        )
    )
    await db.flush()


async def test_sends_to_linked_owners_in_their_language(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(notifier_module, "Bot", FakeBot)
    FakeBot.sent = []
    await add_user(db, Role.OWNER, 111, "ru")
    await add_user(db, Role.OWNER, None, "de")  # not linked
    await add_user(db, Role.USER, 222, "en")  # not an admin

    await make_notifier(db, telegram_bot_token=SecretStr("1:x")).notify_admins(
        "llm_rate_limited", until="20.10 13:00"
    )

    assert FakeBot.sent == [
        (
            111,
            "⏸ Лимит Claude исчерпан, продолжу позже (примерно в 20.10 13:00). "
            "Вакансии копятся в очереди.",
        )
    ]


async def test_no_bot_token_is_not_an_error(db: AsyncSession) -> None:
    await make_notifier(db, telegram_bot_token=None).notify_admins("llm_auth_error")
