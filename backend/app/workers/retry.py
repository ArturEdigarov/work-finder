"""How failed background jobs are retried.

* `LLMDeferred` (pause after a subscription limit, daily cap, auth problem): retry exactly
  at `retry_at`, however many times it takes — the work is queued, never lost.
* `LLMUnavailable` and other transient failures: exponential backoff, limited attempts.
* `LLMInvalidOutput`, `LLMForbidden` and anything else: fail, do not burn the caps.
"""

from procrastinate import BaseRetryStrategy, RetryDecision
from procrastinate.jobs import Job

from app.llm.gate import LLMDeferred
from app.llm.provider import LLMUnavailable

TRANSIENT = (LLMUnavailable, ConnectionError, TimeoutError)


class LLMAwareRetry(BaseRetryStrategy):
    def __init__(self, *, max_attempts: int = 6, base_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.base_seconds = base_seconds

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if isinstance(exception, LLMDeferred):
            return RetryDecision(retry_at=exception.retry_at)
        if isinstance(exception, TRANSIENT) and job.attempts < self.max_attempts:
            # 1, 2, 4, 8, 16, 32 minutes
            return RetryDecision(retry_in={"seconds": self.base_seconds * 2**job.attempts})
        return None


llm_retry = LLMAwareRetry()
