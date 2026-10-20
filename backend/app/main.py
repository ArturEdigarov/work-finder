from app.core.env_guard import enforce_no_api_key

enforce_no_api_key()  # must run before anything else — see CLAUDE.md "Hard Rules"

from collections.abc import AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.api.routers import auth, documents, llm, me  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.workers.queue import queue_app  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # The API only enqueues jobs; `make worker` runs them.
    async with queue_app.open_async():
        yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="work-service", version="0.1.0", lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(llm.router)
    app.include_router(documents.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
