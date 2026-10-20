"""Tiny round-trip used by `make llm-check`: proves auth, structured output and the gate."""

from pydantic import BaseModel, Field

from app.llm.prompts import Prompt
from app.llm.provider import LLMKind


class HealthcheckOut(BaseModel):
    ok: bool
    echo: str = Field(description="The word from the request, unchanged")


PROMPT = Prompt(
    name="healthcheck",
    version="v1",
    kind=LLMKind.CHECK,
    system="You are a health-check endpoint. Answer only with the requested JSON.",
    template="Set ok to true and echo to this word: $word",
    output=HealthcheckOut,
)
