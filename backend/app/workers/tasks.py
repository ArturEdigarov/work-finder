"""Background tasks. LLM tasks use `retry=llm_retry` so limits/pauses reschedule them.

Tasks are thin: load ids → call a domain service. Business logic lives in `app/domain`,
so the API, the bot and the worker share it.
"""

import uuid

from procrastinate.exceptions import AlreadyEnqueued

from app.db.session import get_sessionmaker
from app.domain import profile
from app.llm.gate import get_gate
from app.workers.queue import queue_app
from app.workers.retry import llm_retry


@queue_app.task(name="parse_cv", retry=llm_retry)
async def parse_cv(user_id: str) -> None:
    await profile.run_cv_parse(get_sessionmaker(), get_gate(), uuid.UUID(user_id))


async def enqueue_parse_cv(user_id: uuid.UUID) -> None:
    """At most one *queued* parse per user (queueing_lock) — it reads the current CV anyway —
    and parses of one profile never run concurrently (lock)."""
    try:
        await parse_cv.configure(
            queueing_lock=f"parse_cv:{user_id}", lock=f"profile:{user_id}"
        ).defer_async(user_id=str(user_id))
    except AlreadyEnqueued:
        pass
