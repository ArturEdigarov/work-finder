"""Service → Telegram messages that are not tied to a chat update (e.g. LLM limit reached)."""

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import structlog
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.questions import question_message
from app.bot.texts import t
from app.core.config import Settings, get_settings
from app.db.models import Role, User
from app.domain import profile as profile_domain

log = structlog.get_logger()

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class TelegramAdminNotifier:
    """Sends a localized message to every linked owner/admin. Admin = owner for now."""

    def __init__(self, session_factory: SessionFactory, settings: Settings | None = None) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()

    async def notify_admins(self, key: str, **params: str) -> None:
        token = self._settings.telegram_bot_token
        if token is None or not token.get_secret_value():
            log.warning("admin_notify_skipped_no_bot", key=key)
            return
        async with self._session_factory() as db:
            admins = (
                await db.scalars(
                    select(User).where(
                        User.role.in_([Role.OWNER, Role.ADMIN]),
                        User.telegram_chat_id.is_not(None),
                    )
                )
            ).all()
            recipients = [(u.telegram_chat_id, u.locale) for u in admins]
        if not recipients:
            log.warning("admin_notify_no_recipients", key=key)
            return
        bot = Bot(token.get_secret_value())
        try:
            for chat_id, locale in recipients:
                assert chat_id is not None
                await bot.send_message(chat_id, t(key, locale, **params))
        finally:
            await bot.session.close()
        log.info("admin_notified", key=key, recipients=len(recipients))


async def notify_profile_ready(
    session_factory: SessionFactory, user_id: uuid.UUID, settings: Settings | None = None
) -> None:
    """After a CV parse: "profile ready" + the first open question, if the chat is linked."""
    settings = settings or get_settings()
    token = settings.telegram_bot_token
    if token is None or not token.get_secret_value():
        return
    async with session_factory() as db:
        user = await db.get(User, user_id)
        p = await profile_domain.get_profile(db, user_id)
        if user is None or user.telegram_chat_id is None or p is None:
            return
        chat_id, locale = user.telegram_chat_id, user.locale
        facts, open_qs = len(p.facts), profile_domain.open_questions(p)

    bot = Bot(token.get_secret_value())
    try:
        await bot.send_message(chat_id, t("profile_ready", locale, facts=facts))
        if open_qs:
            await bot.send_message(chat_id, t("questions_intro", locale, count=len(open_qs)))
            text, keyboard = question_message(open_qs[0], locale)
            await bot.send_message(chat_id, text, reply_markup=keyboard)
    finally:
        await bot.session.close()
    log.info("profile_ready_notified", user_id=str(user_id), questions=len(open_qs))
