"""Account use-cases. Shared by the HTTP API and the Telegram bot.

Functions here flush but never commit — the caller owns the transaction.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import email_lookup_hash, normalize_email, token_hash
from app.db.models import (
    AuditLog,
    AuthSession,
    Consent,
    LlmUsage,
    Role,
    TelegramLinkToken,
    User,
)

_hasher = PasswordHasher()  # argon2id with library defaults
# Verified against when the user does not exist, so login timing does not reveal
# which emails are registered.
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")

SUPPORTED_LOCALES = ("de", "en", "ru", "uk")


class AccountError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


async def audit(db: AsyncSession, user_id: uuid.UUID | None, action: str) -> None:
    db.add(AuditLog(user_id=user_id, action=action))


async def register(
    db: AsyncSession, *, email: str, password: str, consent_version: str, locale: str
) -> User:
    settings = get_settings()
    if consent_version != settings.consent_version:
        raise AccountError("consent_required")
    if len(password) < settings.password_min_length:
        raise AccountError("password_too_short")
    if locale not in SUPPORTED_LOCALES:
        raise AccountError("unsupported_locale")

    email_hash = email_lookup_hash(email)
    if await db.scalar(select(User.id).where(User.email_hash == email_hash)):
        raise AccountError("email_taken")

    is_owner = settings.owner_email is not None and normalize_email(email) == normalize_email(
        settings.owner_email
    )
    user = User(
        email=normalize_email(email),
        email_hash=email_hash,
        password_hash=_hasher.hash(password),
        role=Role.OWNER if is_owner else Role.USER,
        locale=locale,
    )
    db.add(user)
    await db.flush()
    db.add(Consent(user_id=user.id, version=consent_version))
    await audit(db, user.id, "account.registered")
    await db.flush()
    return user


def _verify_password(user: User | None, password: str) -> bool:
    try:
        return _hasher.verify(user.password_hash if user else _DUMMY_HASH, password) and (
            user is not None
        )
    except (VerificationError, InvalidHashError):
        return False


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.email_hash == email_lookup_hash(email)))
    if not _verify_password(user, password):
        return None
    assert user is not None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    await audit(db, user.id, "account.login")
    return user


async def create_session(db: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=_now() + timedelta(days=get_settings().session_ttl_days),
        )
    )
    await db.flush()
    return token


async def user_by_session_token(db: AsyncSession, token: str) -> User | None:
    session = await db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(token), AuthSession.expires_at > _now()
        )
    )
    return session.user if session else None


async def revoke_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))


async def set_locale(db: AsyncSession, user: User, locale: str) -> None:
    if locale not in SUPPORTED_LOCALES:
        raise AccountError("unsupported_locale")
    user.locale = locale
    await db.flush()


async def create_telegram_link_token(db: AsyncSession, user: User) -> str:
    # Telegram /start payload: max 64 chars of [A-Za-z0-9_-]; token_urlsafe(24) → 32 chars.
    token = secrets.token_urlsafe(24)
    await db.execute(delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))
    db.add(
        TelegramLinkToken(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=_now() + timedelta(minutes=get_settings().telegram_link_ttl_minutes),
        )
    )
    await db.flush()
    return token


async def link_telegram(db: AsyncSession, *, token: str, chat_id: int) -> User:
    link = await db.scalar(
        select(TelegramLinkToken).where(TelegramLinkToken.token_hash == token_hash(token))
    )
    if link is None or link.expires_at <= _now():
        raise AccountError("link_token_invalid")
    other = await db.scalar(select(User).where(User.telegram_chat_id == chat_id))
    if other is not None and other.id != link.user_id:
        raise AccountError("chat_already_linked")

    user = await db.get_one(User, link.user_id)
    user.telegram_chat_id = chat_id
    await db.delete(link)
    await audit(db, user.id, "account.telegram_linked")
    await db.flush()
    return user


async def unlink_telegram(db: AsyncSession, user: User) -> None:
    user.telegram_chat_id = None
    await audit(db, user.id, "account.telegram_unlinked")
    await db.flush()


async def export_user_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """GDPR Art. 15/20: everything we store about the user, in readable form."""
    consents = (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
    usage = (
        await db.scalars(select(LlmUsage).where(LlmUsage.user_id == user.id).order_by(LlmUsage.day))
    ).all()
    return {
        "exported_at": _now().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "locale": user.locale,
            "telegram_linked": user.telegram_chat_id is not None,
            "created_at": user.created_at.isoformat(),
        },
        "consents": [
            {
                "version": c.version,
                "accepted_at": c.accepted_at.isoformat(),
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in consents
        ],
        "llm_usage": [{"day": u.day.isoformat(), "kind": u.kind, "count": u.count} for u in usage],
    }


async def delete_account(db: AsyncSession, user: User, *, password: str) -> None:
    """GDPR Art. 17: hard delete. FKs cascade; audit rows keep only a NULL user_id."""
    if not _verify_password(user, password):
        raise AccountError("invalid_password")
    await audit(db, None, "account.deleted")
    await db.delete(user)
    await db.flush()
