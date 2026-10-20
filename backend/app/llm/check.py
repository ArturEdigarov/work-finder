"""`make llm-check`: one tiny real call through LLMGate on behalf of the owner.

Verifies the whole path: no API key, Claude Code login (or CLAUDE_CODE_OAUTH_TOKEN on the
VPS), structured output, gate checks and usage accounting. Counts against the `check` cap.
Exit code: 0 ok, 1 call failed or deferred, 2 setup problem.
"""

from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

import asyncio  # noqa: E402
import secrets  # noqa: E402
import sys  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.crypto import email_lookup_hash  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.models import Role, User  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.llm.gate import LLMDeferred, LLMForbidden, get_gate  # noqa: E402
from app.llm.prompts import healthcheck  # noqa: E402
from app.llm.provider import LLMError  # noqa: E402


async def run() -> int:
    configure_logging()
    settings = get_settings()
    if not settings.owner_email:
        print("SETUP: OWNER_EMAIL is not set in .env")
        return 2
    async with get_sessionmaker()() as db:
        owner_id = await db.scalar(
            select(User.id).where(
                User.email_hash == email_lookup_hash(settings.owner_email),
                User.role == Role.OWNER,
            )
        )
    if owner_id is None:
        print("SETUP: no owner account yet — register on the website with OWNER_EMAIL")
        return 2

    word = secrets.token_hex(4)
    req = healthcheck.PROMPT.build(user_id=owner_id, word=word)
    try:
        result = await get_gate().call(req)
    except LLMDeferred as exc:
        local = exc.retry_at.astimezone(ZoneInfo(settings.timezone))
        print(f"DEFERRED: {exc.reason}, retry after {local:%d.%m %H:%M}")
        return 1
    except (LLMForbidden, LLMError) as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1

    if not result.data.ok or result.data.echo != word:
        print(f"FAILED: unexpected answer {result.data!r}")
        return 1
    tokens = result.usage.get("input_tokens", 0) + result.usage.get("output_tokens", 0)
    print(
        f"OK: provider={result.provider} model={result.model} "
        f"{result.duration_ms} ms, ~{tokens} tokens (+cache), prompt={req.prompt_version}"
    )
    return 0


async def main() -> int:
    try:
        return await run()
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
