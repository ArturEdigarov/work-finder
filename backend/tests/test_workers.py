from datetime import UTC, datetime, timedelta

import pytest
from procrastinate import App
from procrastinate.jobs import Job
from procrastinate.testing import InMemoryConnector

from app.core.config import Settings
from app.llm.gate import LLMDeferred, LLMForbidden
from app.llm.provider import LLMInvalidOutput, LLMUnavailable
from app.workers.retry import LLMAwareRetry, llm_retry

RETRY_AT = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


def job(attempts: int = 0) -> Job:
    return Job(queue="default", lock=None, queueing_lock=None, task_name="t", attempts=attempts)


def test_deferred_retries_exactly_at_retry_at_without_limit() -> None:
    for attempts in (0, 5, 50):
        decision = llm_retry.get_retry_decision(
            exception=LLMDeferred(RETRY_AT, "rate_limited"), job=job(attempts)
        )
        assert decision is not None and decision.retry_at == RETRY_AT


def test_transient_errors_back_off_and_give_up() -> None:
    strategy = LLMAwareRetry(max_attempts=3, base_seconds=60)
    delays: list[int | None] = []
    for attempts in range(4):
        now = datetime.now(UTC)
        decision = strategy.get_retry_decision(exception=LLMUnavailable("x"), job=job(attempts))
        delays.append(round((decision.retry_at - now).total_seconds()) if decision else None)
    assert delays == [60, 120, 240, None]


@pytest.mark.parametrize(
    "exc", [LLMInvalidOutput("bad"), LLMForbidden("owner only"), ValueError("bug")]
)
def test_permanent_errors_are_not_retried(exc: Exception) -> None:
    assert llm_retry.get_retry_decision(exception=exc, job=job()) is None


def test_dsn_for_psycopg() -> None:
    settings = Settings(database_url="postgresql+asyncpg://u:p@127.0.0.1:5432/db")
    assert settings.database_dsn == "postgresql://u:p@127.0.0.1:5432/db"


async def test_worker_reschedules_deferred_llm_jobs() -> None:
    """A real procrastinate worker run (in-memory queue) with the LLM-aware strategy."""
    connector = InMemoryConnector()
    app = App(connector=connector)
    retry_at = datetime.now(UTC) + timedelta(hours=2)

    @app.task(name="paused", retry=llm_retry)
    async def paused() -> None:
        raise LLMDeferred(retry_at, "rate_limited")

    @app.task(name="flaky", retry=llm_retry)
    async def flaky() -> None:
        raise LLMUnavailable("timeout")

    @app.task(name="broken", retry=llm_retry)
    async def broken() -> None:
        raise LLMInvalidOutput("bad json")

    @app.task(name="fine", retry=llm_retry)
    async def fine() -> None:
        return None

    async with app.open_async():
        for task in (paused, flaky, broken, fine):
            await task.defer_async()
        await app.run_worker_async(wait=False, install_signal_handlers=False)

    jobs = {row["task_name"]: row for row in connector.jobs.values()}
    assert jobs["paused"]["status"] == "todo"
    assert jobs["paused"]["scheduled_at"] == retry_at
    assert jobs["flaky"]["status"] == "todo"
    assert jobs["flaky"]["scheduled_at"] > datetime.now(UTC) + timedelta(seconds=50)
    assert jobs["broken"]["status"] == "failed"
    assert jobs["fine"]["status"] == "succeeded"
