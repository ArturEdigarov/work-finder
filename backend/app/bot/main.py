from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

import asyncio  # noqa: E402
import sys  # noqa: E402
import uuid  # noqa: E402

import structlog  # noqa: E402
from aiogram import Bot, Dispatcher, F, Router  # noqa: E402
from aiogram.filters import Command, CommandObject, CommandStart  # noqa: E402
from aiogram.types import CallbackQuery, Message  # noqa: E402

from app.bot.questions import SKIP_PREFIX, question_message  # noqa: E402
from app.bot.texts import t  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.domain import accounts, profile  # noqa: E402
from app.domain.accounts import AccountError  # noqa: E402

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


def _tg_locale(message: Message) -> str | None:
    return message.from_user.language_code if message.from_user else None


async def _send_next_question(message: Message, user_id: uuid.UUID, locale: str) -> None:
    """Ask the first open question, or say that there are none left."""
    async with get_sessionmaker()() as db:
        p = await profile.get_profile(db, user_id)
        open_qs = profile.open_questions(p) if p else []
    if not open_qs:
        await message.answer(t("all_answered", locale))
        return
    text, keyboard = question_message(open_qs[0], locale)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("questions"))
async def on_questions(message: Message) -> None:
    async with get_sessionmaker()() as db:
        user = await accounts.user_by_chat(db, message.chat.id)
        if user is None:
            await message.answer(t("not_linked", _tg_locale(message)))
            return
        p = await profile.get_profile(db, user.id)
        open_qs = profile.open_questions(p) if p else []
        locale = user.locale
    if p is None:
        await message.answer(t("no_profile", locale))
    elif not open_qs:
        await message.answer(t("no_questions", locale))
    else:
        await message.answer(t("questions_intro", locale, count=len(open_qs)))
        text, keyboard = question_message(open_qs[0], locale)
        await message.answer(text, reply_markup=keyboard)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    """A plain message answers the first open question (questions are asked one by one)."""
    async with get_sessionmaker()() as db:
        user = await accounts.user_by_chat(db, message.chat.id)
        if user is None:
            await message.answer(t("not_linked", _tg_locale(message)))
            return
        locale, user_id = user.locale, user.id
        p = await profile.get_profile(db, user_id)
        open_qs = profile.open_questions(p) if p else []
        if not open_qs:
            await message.answer(t("no_questions" if p else "no_profile", locale))
            return
        try:
            await profile.answer_question(db, user_id, open_qs[0]["id"], message.text or "")
        except AccountError:
            await message.answer(t("no_questions", locale))
            return
        await db.commit()
    log.info("profile_question_answered", user_id=str(user_id), via="bot")
    await message.answer(t("answer_saved", locale))
    await _send_next_question(message, user_id, locale)


@router.callback_query(F.data.startswith(SKIP_PREFIX))
async def on_skip(callback: CallbackQuery) -> None:
    question_id = (callback.data or "").removeprefix(SKIP_PREFIX)
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    async with get_sessionmaker()() as db:
        user = await accounts.user_by_chat(db, message.chat.id)
        if user is None:
            await callback.answer()
            return
        locale, user_id = user.locale, user.id
        try:
            await profile.dismiss_question(db, user_id, question_id)
            await db.commit()
        except AccountError:
            pass  # already answered/removed on the website — just move on
    await callback.answer(t("skipped", locale))
    await message.edit_reply_markup(reply_markup=None)
    await _send_next_question(message, user_id, locale)


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
