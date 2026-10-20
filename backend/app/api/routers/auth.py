from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import DbSession, auth_rate_limit, get_session_token
from app.api.schemas import ConsentInfoOut, LoginIn, RegisterIn, UserOut
from app.api.serializers import user_out
from app.core.config import get_settings
from app.domain import accounts

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


@router.get("/consent", response_model=ConsentInfoOut)
async def consent_info() -> ConsentInfoOut:
    return ConsentInfoOut(version=get_settings().consent_version)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(body: RegisterIn, db: DbSession, response: Response) -> UserOut:
    try:
        user = await accounts.register(
            db,
            email=body.email,
            password=body.password,
            consent_version=body.consent_version,
            locale=body.locale,
        )
    except accounts.AccountError as exc:
        code = status.HTTP_409_CONFLICT if exc.code == "email_taken" else 422
        raise HTTPException(code, exc.code) from exc
    token = await accounts.create_session(db, user)
    await db.commit()
    _set_session_cookie(response, token)
    return user_out(user)


@router.post("/login", response_model=UserOut, dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginIn, db: DbSession, response: Response) -> UserOut:
    user = await accounts.authenticate(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    token = await accounts.create_session(db, user)
    await db.commit()
    _set_session_cookie(response, token)
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: DbSession, response: Response, token: str | None = Depends(get_session_token)
) -> None:
    if token:
        await accounts.revoke_session(db, token)
        await db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")
