import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.db.types import EncryptedString


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
