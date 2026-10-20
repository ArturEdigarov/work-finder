import base64
import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Deterministic test-only secrets; never the real ones from .env.
os.environ["FIELD_ENCRYPTION_KEYS"] = "1:" + base64.b64encode(b"k" * 32).decode()
os.environ["EMAIL_HASH_KEY"] = base64.b64encode(b"h" * 32).decode()
os.environ["OWNER_EMAIL"] = "owner@example.com"
os.environ["TELEGRAM_BOT_USERNAME"] = "work_service_test_bot"
os.environ["CONSENT_VERSION"] = "test-1"
os.environ["ENV"] = "test"

from app.api.deps import auth_rate_limit
from app.core.config import get_settings
from app.core.crypto import get_cipher
from app.db.session import get_db
from app.main import app

TEST_DB_URL = get_settings().test_database_url
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Run real migrations (down to base, then up) so tests also cover them."""
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.attributes["database_url"] = TEST_DB_URL
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    get_settings.cache_clear()
    get_cipher.cache_clear()
    auth_rate_limit.reset()
    yield
    get_settings.cache_clear()
    get_cipher.cache_clear()


@pytest.fixture
async def db(migrated_db: None) -> AsyncIterator[AsyncSession]:
    """Each test runs inside a transaction that is rolled back afterwards.
    App code may call commit() — with create_savepoint it only releases a savepoint."""
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


PASSWORD = "correct horse battery"


async def register(client: AsyncClient, email: str = "user@example.com") -> dict[str, object]:
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "consent_version": "test-1", "locale": "ru"},
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, object] = resp.json()
    return data
