from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

from fastapi import FastAPI  # noqa: E402

from app.api.routers import auth, me  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="work-service", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(me.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
