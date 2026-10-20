import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.domain import accounts

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_session_token(request: Request) -> str | None:
    return request.cookies.get(get_settings().session_cookie_name)


async def current_user(
    db: DbSession, token: Annotated[str | None, Depends(get_session_token)]
) -> User:
    user = await accounts.user_by_session_token(db, token) if token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


class RateLimiter:
    """In-memory sliding window. Fine for a single API process on localhost;
    move to Postgres/Redis when running several instances."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    async def __call__(self, request: Request) -> None:
        key = f"{request.url.path}:{request.client.host if request.client else '-'}"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
        hits.append(now)


auth_rate_limit = RateLimiter(limit=10, window_seconds=60)
