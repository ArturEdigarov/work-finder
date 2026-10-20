"""Versioned prompt registry.

Each prompt is a module in this package with a `PROMPT` constant: system text, a user
template (`string.Template`, `$name` placeholders — safe with JSON braces in the text)
and a Pydantic output model whose JSON schema is passed to the provider.

Bump `version` whenever the wording or the output model changes: it is logged with
every call, so results can be traced back to the exact prompt.
"""

import uuid
from dataclasses import dataclass
from string import Template

from pydantic import BaseModel

from app.llm.provider import LLMKind, LLMRequest


@dataclass(frozen=True, kw_only=True)
class Prompt[T: BaseModel]:
    name: str
    version: str
    kind: LLMKind
    system: str
    template: str
    output: type[T]

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    def build(self, *, user_id: uuid.UUID, **params: str) -> LLMRequest[T]:
        """Missing placeholders raise KeyError — a prompt is never sent half-filled."""
        return LLMRequest(
            kind=self.kind,
            user_id=user_id,
            system=self.system,
            prompt=Template(self.template).substitute(params),
            output=self.output,
            prompt_version=self.id,
        )
