from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

import asyncio  # noqa: E402
import sys  # noqa: E402

import structlog  # noqa: E402
from aiogram import Bot, Dispatcher, Router  # noqa: E402
from aiogram.filters import CommandObject, CommandStart  # noqa: E402
from aiogram.types import Message  # noqa: E402

from app.bot.texts import t  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.domain import accounts  # noqa: E402

log = structlog.get_logger()
router = Router()


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject) -> None:
    tg_locale = message.from_user.language_code if message.from_user else None
    if not command.args:
        await message.answer(t("start_no_token", tg_locale))
        return

    async with get_sessionmaker()() as db:
        try:
            user = await accounts.link_telegram(db, token=command.args, chat_id=message.chat.id)
        except accounts.AccountError as exc:
            key = "chat_taken" if exc.code == "chat_already_linked" else "link_invalid"
            await message.answer(t(key, tg_locale))
            return
        await db.commit()
    log.info("telegram_linked", user_id=str(user.id))
    await message.answer(t("linked", user.locale))


async def run() -> None:
    configure_logging()
    token = get_settings().telegram_bot_token
    if token is None or not token.get_secret_value():
        sys.exit("TELEGRAM_BOT_TOKEN is not set in .env — create a bot via @BotFather.")
    bot = Bot(token.get_secret_value())
    dp = Dispatcher()
    dp.include_router(router)
    log.info("bot_started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
