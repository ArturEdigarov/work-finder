import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Locale = Literal["de", "en", "ru", "uk"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    consent_version: str
    locale: Locale = "ru"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    locale: str
    telegram_linked: bool
    created_at: datetime


class UpdateMeIn(BaseModel):
    locale: Locale


class TelegramLinkOut(BaseModel):
    url: str
    expires_in_minutes: int


class DeleteMeIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ConsentInfoOut(BaseModel):
    version: str


class ErrorOut(BaseModel):
    detail: str


class LlmKindUsageOut(BaseModel):
    kind: Literal["parse", "score", "draft", "check"]
    used: int
    cap: int


class LlmStatusOut(BaseModel):
    provider: str
    available: bool
    paused_until: datetime | None
    day: date
    usage: list[LlmKindUsageOut]


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: Literal["extracted", "no_text"]
    text_chars: int
    created_at: datetime


class FactOut(BaseModel):
    id: str
    type: str
    value: dict[str, object]
    source: Literal["cv", "user_answer", "user_edit"]


class ProfileOut(BaseModel):
    status: Literal["queued", "parsing", "ready", "failed", "unavailable"]
    version: int
    parsed_at: datetime | None
    prompt_version: str | None
    facts: list[FactOut]
