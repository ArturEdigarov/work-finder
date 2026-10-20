"""Worker process: `make worker`. The only process that calls the LLM in production."""

from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

import asyncio  # noqa: E402

import structlog  # noqa: E402

from app.core.logging import configure_logging  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.workers.queue import queue_app  # noqa: E402

log = structlog.get_logger()

# LLM calls are serialized by the gate anyway; a second slot keeps cheap jobs moving.
CONCURRENCY = 2


async def run() -> None:
    configure_logging()
    log.info("worker_started", concurrency=CONCURRENCY)
    try:
        async with queue_app.open_async():
            await queue_app.run_worker_async(concurrency=CONCURRENCY)
    finally:
        await get_engine().dispose()
        log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
