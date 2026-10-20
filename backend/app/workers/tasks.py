"""Background tasks. LLM tasks use `retry=llm_retry` so limits/pauses reschedule them.

Tasks are thin: load ids → call a domain service. Business logic lives in `app/domain`,
so the API, the bot and the worker share it.
"""

import uuid

import structlog
from procrastinate.exceptions import AlreadyEnqueued

from app.bot.notifier import notify_profile_ready
from app.db.session import get_sessionmaker
from app.domain import profile
from app.llm.gate import get_gate
from app.workers.queue import queue_app
from app.workers.retry import llm_retry

log = structlog.get_logger()


@queue_app.task(name="parse_cv", retry=llm_retry)
async def parse_cv(user_id: str) -> None:
    uid = uuid.UUID(user_id)
    if await profile.run_cv_parse(get_sessionmaker(), get_gate(), uid):
        try:
            await notify_profile_ready(get_sessionmaker(), uid)
        except Exception:
            # The profile is saved; a lost Telegram message must not fail (and re-run) the parse.
            log.exception("profile_ready_notify_failed", user_id=user_id)


async def enqueue_parse_cv(user_id: uuid.UUID) -> None:
    """At most one *queued* parse per user (queueing_lock) — it reads the current CV anyway —
    and parses of one profile never run concurrently (lock)."""
    try:
        await parse_cv.configure(
            queueing_lock=f"parse_cv:{user_id}", lock=f"profile:{user_id}"
        ).defer_async(user_id=str(user_id))
    except AlreadyEnqueued:
        pass
