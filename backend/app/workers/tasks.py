"""Background tasks. LLM tasks use `retry=llm_retry` so limits/pauses reschedule them.

Tasks are thin: load ids → call a domain service → commit. Business logic lives in
`app/domain`, so the API, the bot and the worker share it.
"""

from app.workers.queue import queue_app  # noqa: F401  (tasks register on this app)

# Phase 2.3 adds `parse_cv`.
