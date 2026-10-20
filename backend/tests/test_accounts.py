import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, AuthSession, Consent, User
from app.domain import accounts
from tests.conftest import PASSWORD, register


async def test_register_sets_session_and_consent(client: AsyncClient, db: AsyncSession) -> None:
    user = await register(client)
    assert user["role"] == "user"
    assert (await client.get("/me")).json()["email"] == "user@example.com"
    consents = (await db.scalars(select(Consent))).all()
    assert [c.version for c in consents] == ["test-1"]


async def test_email_is_encrypted_at_rest(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    raw = await db.scalar(text("SELECT email_enc FROM users"))
    assert raw is not None and raw.startswith("v1:") and "example" not in raw


async def test_owner_role_from_config(client: AsyncClient) -> None:
    user = await register(client, email="Owner@Example.com")
    assert user["role"] == "owner"


async def test_consent_is_required(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": PASSWORD, "consent_version": "old"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "consent_required"


async def test_short_password_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "short", "consent_version": "test-1"},
    )
    assert resp.json()["detail"] == "password_too_short"


async def test_duplicate_email(client: AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    resp = await client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": PASSWORD, "consent_version": "test-1"},
    )
    assert resp.status_code == 409


async def test_login_logout(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    await client.post("/auth/logout")
    assert (await client.get("/me")).status_code == 401

    bad = await client.post("/auth/login", json={"email": "user@example.com", "password": "x"})
    assert bad.status_code == 401
    ok = await client.post("/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert (await client.get("/me")).status_code == 200
    # only the hash of the token is stored
    token = client.cookies.get("ws_session")
    hashes = (await db.scalars(select(AuthSession.token_hash))).all()
    assert token not in hashes


async def test_login_rate_limited(client: AsyncClient) -> None:
    for _ in range(10):
        await client.post("/auth/login", json={"email": "x@example.com", "password": "x"})
    resp = await client.post("/auth/login", json={"email": "x@example.com", "password": "x"})
    assert resp.status_code == 429


async def test_update_locale(client: AsyncClient) -> None:
    await register(client)
    resp = await client.patch("/me", json={"locale": "de"})
    assert resp.json()["locale"] == "de"


async def test_telegram_link_flow(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    resp = await client.post("/me/telegram-link")
    url = resp.json()["url"]
    assert url.startswith("https://t.me/work_service_test_bot?start=")
    token = url.split("start=")[1]

    user = await accounts.link_telegram(db, token=token, chat_id=4242)
    assert user.telegram_chat_id == 4242
    assert (await client.get("/me")).json()["telegram_linked"] is True

    with pytest.raises(accounts.AccountError, match="link_token_invalid"):
        await accounts.link_telegram(db, token=token, chat_id=4242)  # one-time


async def test_chat_cannot_be_linked_twice(client: AsyncClient, db: AsyncSession) -> None:
    await register(client, "a@example.com")
    t1 = (await client.post("/me/telegram-link")).json()["url"].split("start=")[1]
    await accounts.link_telegram(db, token=t1, chat_id=1)

    client.cookies.clear()
    await register(client, "b@example.com")
    t2 = (await client.post("/me/telegram-link")).json()["url"].split("start=")[1]
    with pytest.raises(accounts.AccountError, match="chat_already_linked"):
        await accounts.link_telegram(db, token=t2, chat_id=1)


async def test_export(client: AsyncClient) -> None:
    await register(client)
    resp = await client.get("/me/export")
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["account"]["email"] == "user@example.com"
    assert data["consents"][0]["version"] == "test-1"


async def test_delete_account_cascades(client: AsyncClient, db: AsyncSession) -> None:
    await register(client)
    assert (await client.post("/me/delete", json={"password": "wrong"})).status_code == 403

    resp = await client.post("/me/delete", json={"password": PASSWORD})
    assert resp.status_code == 204
    assert (await client.get("/me")).status_code == 401
    for model in (User, AuthSession, Consent):
        assert await db.scalar(select(func.count()).select_from(model)) == 0
    # audit rows survive, but without a link to the person
    assert await db.scalar(select(func.count()).where(AuditLog.user_id.is_not(None))) == 0
