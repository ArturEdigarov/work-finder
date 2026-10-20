"""Background job queue on Postgres (procrastinate). Worker: `make worker`.

Enqueue from the API/bot only *after* committing the data the job needs — the job runs on
another connection and must see it.
"""

from procrastinate import App, PsycopgConnector

from app.core.config import get_settings

queue_app = App(
    connector=PsycopgConnector(conninfo=get_settings().database_dsn),
    import_paths=["app.workers.tasks"],
)
