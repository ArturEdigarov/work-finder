"""Profile questions in Telegram: one question at a time, answered with a plain message.

Used by the bot handlers and by the worker's "profile ready" notification, so both
render questions the same way.
"""

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.texts import t

SKIP_PREFIX = "q_skip:"


def question_message(question: dict[str, Any], locale: str) -> tuple[str, InlineKeyboardMarkup]:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("skip_button", locale), callback_data=f"{SKIP_PREFIX}{question['id']}"
                )
            ]
        ]
    )
    return t("question", locale, question=question["question"]), keyboard
