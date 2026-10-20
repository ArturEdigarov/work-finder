COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: db-up db-down migrate api bot web test lint check gen-types keygen llm-check worker

db-up:
	$(COMPOSE) up -d --wait

db-down:
	$(COMPOSE) stop

migrate:
	cd backend && uv run alembic upgrade head

api:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

worker:
	cd backend && uv run python -m app.workers.main

bot:
	cd backend && uv run python -m app.bot.main

web:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && pnpm lint && pnpm format:check && pnpm typecheck

check: lint test

gen-types:
	cd backend && uv run python -m app.openapi > ../frontend/openapi.json
	cd frontend && pnpm gen-types

keygen:
	cd backend && uv run python -m app.core.keygen

# One tiny real Claude call through LLMGate (counts against the daily `check` cap)
llm-check:
	cd backend && uv run python -m app.llm.check
