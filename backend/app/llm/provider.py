"""LLM provider contract.

Nothing outside `app/llm/` calls a provider directly — everything goes through
`LLMGate` (see CLAUDE.md "Hard Rules — Money & LLM" and ADR-0001).
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class LLMKind(enum.StrEnum):
    """Each kind has its own daily cap and model setting."""

    PARSE = "parse"  # CV → structured profile
    SCORE = "score"  # vacancy fit
    DRAFT = "draft"  # cover letter + CV adaptation
    CHECK = "check"  # `make llm-check` health check


@dataclass(frozen=True, kw_only=True)
class LLMRequest[T: BaseModel]:
    kind: LLMKind
    user_id: uuid.UUID
    system: str
    prompt: str
    output: type[T]  # the response is validated against this model's JSON schema
    prompt_version: str = "v1"

    def json_schema(self) -> dict[str, Any]:
        return self.output.model_json_schema()


@dataclass(frozen=True, kw_only=True)
class LLMResult[T: BaseModel]:
    data: T
    provider: str
    model: str | None = None
    duration_ms: int = 0
    usage: dict[str, int] = field(default_factory=dict)  # token counts, if reported


class LLMError(Exception):
    """Base class for provider failures."""


class LLMRateLimited(LLMError):
    """The provider's usage limit is exhausted. The gate pauses all calls until reset."""

    def __init__(self, reset_at: datetime | None = None, message: str = "rate limited") -> None:
        super().__init__(message)
        self.reset_at = reset_at


class LLMAuthError(LLMError):
    """Not logged in / token expired. Needs a human: the admin is notified."""


class LLMInvalidOutput(LLMError):
    """The response did not match the requested schema (after one retry)."""


class LLMUnavailable(LLMError):
    """Transient failure: timeout, crash, network. Safe to retry later."""


class LLMProvider(Protocol):
    name: str
    # True for providers billed to the owner's personal subscription:
    # the gate allows them for role=owner only.
    subscription: bool

    async def complete[T: BaseModel](self, req: LLMRequest[T]) -> LLMResult[T]: ...
