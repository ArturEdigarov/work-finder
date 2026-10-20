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
