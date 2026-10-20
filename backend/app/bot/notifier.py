"""Service → Telegram messages that are not tied to a chat update (e.g. LLM limit reached)."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import structlog
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.texts import t
from app.core.config import Settings, get_settings
from app.db.models import Role, User

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
