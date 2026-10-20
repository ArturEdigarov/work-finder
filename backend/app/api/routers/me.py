from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import DeleteMeIn, TelegramLinkOut, UpdateMeIn, UserOut
from app.api.serializers import user_out
from app.core.config import get_settings
from app.domain import accounts

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("", response_model=UserOut)
async def update_me(body: UpdateMeIn, user: CurrentUser, db: DbSession) -> UserOut:
    await accounts.set_locale(db, user, body.locale)
    await db.commit()
    return user_out(user)


@router.post("/telegram-link", response_model=TelegramLinkOut)
async def telegram_link(user: CurrentUser, db: DbSession) -> TelegramLinkOut:
    settings = get_settings()
    if not settings.telegram_bot_username:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram_not_configured")
    token = await accounts.create_telegram_link_token(db, user)
    await db.commit()
    return TelegramLinkOut(
        url=f"https://t.me/{settings.telegram_bot_username}?start={token}",
        expires_in_minutes=settings.telegram_link_ttl_minutes,
    )


@router.delete("/telegram-link", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_unlink(user: CurrentUser, db: DbSession) -> None:
    await accounts.unlink_telegram(db, user)
    await db.commit()


@router.get("/export")
async def export_me(user: CurrentUser, db: DbSession) -> JSONResponse:
    data: dict[str, Any] = await accounts.export_user_data(db, user)
    await db.commit()
    return JSONResponse(
        data,
        headers={"Content-Disposition": 'attachment; filename="work-service-export.json"'},
    )


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(body: DeleteMeIn, user: CurrentUser, db: DbSession, response: Response) -> None:
    try:
        await accounts.delete_account(db, user, password=body.password)
    except accounts.AccountError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.code) from exc
    await db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")
