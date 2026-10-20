"""In-memory provider for tests and local runs without spending the subscription."""

from collections import deque
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm.provider import LLMInvalidOutput, LLMRequest, LLMResult

FakeResponse = dict[str, Any] | Exception


class FakeProvider:
    name = "fake"

    def __init__(self, responses: list[FakeResponse] | None = None, *, subscription: bool = True):
        # Defaults to subscription=True so tests exercise the owner-only rule.
        self.subscription = subscription
        self._responses: deque[FakeResponse] = deque(responses or [])
        self.calls: list[LLMRequest[Any]] = []

    def queue(self, *responses: FakeResponse) -> None:
        self._responses.extend(responses)

    async def complete[T: BaseModel](self, req: LLMRequest[T]) -> LLMResult[T]:
        self.calls.append(req)
        if not self._responses:
            raise AssertionError("FakeProvider: no queued response")
        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        try:
            data = req.output.model_validate(response)
        except ValidationError as exc:
            raise LLMInvalidOutput(str(exc)) from exc
        return LLMResult(data=data, provider=self.name, model="fake")
