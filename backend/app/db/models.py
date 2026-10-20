import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.db.types import EncryptedBytes, EncryptedJSON, EncryptedString


class Role(enum.StrEnum):
    OWNER = "owner"  # the only role allowed to use the Claude subscription provider
    USER = "user"
    ADMIN = "admin"


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'user', 'admin')", name="role_valid"),)

    email: Mapped[str] = mapped_column("email_enc", EncryptedString("users.email"))
    email_hash: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=Role.USER)
    locale: Mapped[str] = mapped_column(String(8), default="ru")
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)

    consents: Mapped[list["Consent"]] = relationship(
        back_populates="user", passive_deletes=True, order_by="Consent.accepted_at"
    )


class AuthSession(UUIDPk, Base):
    """Server-side session: revocable, deleted together with the user."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(lazy="joined")


class Consent(UUIDPk, Base):
    __tablename__ = "consents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="consents")


class TelegramLinkToken(Base):
    """One-time token for /start deep-link that binds a Telegram chat to an account."""

    __tablename__ = "telegram_link_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(UUIDPk, Base):
    """Who did what and when. No personal data in `action`."""

    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmUsage(UUIDPk, Base):
    """LLM calls that reached the model, per user, kind and day (Europe/Berlin) — daily caps."""

    __tablename__ = "llm_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "day", name="uq_llm_usage_user_kind_day"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)


class LlmState(Base):
    """Per-provider pause state. One row per provider name."""

    __tablename__ = "llm_state"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the "limit, will continue later" message was sent for the current pause.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Consecutive rate-limit hits without a successful call — drives the backoff.
    pause_streak: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentStatus(enum.StrEnum):
    EXTRACTED = "extracted"  # text is available
    NO_TEXT = "no_text"  # e.g. a scanned PDF — ask for DOCX / text PDF


class Document(UUIDPk, Base):
    """Uploaded file (Lebenslauf). File and extracted text are encrypted at rest."""

    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("status IN ('extracted', 'no_text')", name="status_valid"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="cv")
    filename: Mapped[str] = mapped_column("filename_enc", EncryptedString("documents.filename"))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    file: Mapped[bytes] = mapped_column("file_enc", EncryptedBytes("documents.file"))
    text: Mapped[str | None] = mapped_column("text_enc", EncryptedString("documents.text"))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileStatus(enum.StrEnum):
    QUEUED = "queued"  # waiting for the worker (or for an LLM pause to end)
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"  # the model returned unusable output twice
    UNAVAILABLE = "unavailable"  # no LLM provider for this user (subscription is owner-only)


class Profile(UUIDPk, Timestamps, Base):
    """Structured profile = a list of facts. Letters and CV variants reference fact ids.

    `facts`: [{"id": "f_ab12cd34", "type": "experience", "value": {...},
               "source": "cv" | "user_answer" | "user_edit"}]
    Re-parsing replaces only `source == "cv"` facts.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'parsing', 'ready', 'failed', 'unavailable')",
            name="status_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(16))
    facts: Mapped[list[dict[str, object]]] = mapped_column(
        "facts_enc", EncryptedJSON("profiles.facts"), default=list
    )
    # Questions about gaps: [{"id": "q_…", "field", "question", "status": open|answered|
    # dismissed, "fact_ids": [...]}]. Column/AAD names are historical — keep them stable.
    questions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        "suggested_questions_enc", EncryptedJSON("profiles.suggested_questions")
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=0)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
