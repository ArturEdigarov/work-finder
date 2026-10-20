# work-finder

Job-search assistant for the German market (any profession): collects vacancies from user-selected sources, scores fit against the user's Lebenslauf, drafts a cover letter and a truthful CV adaptation, and lets the user apply in one click via Telegram bot or website.

- Product: [docs/PRODUCT.md](docs/PRODUCT.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Collaboration rules: [CLAUDE.md](CLAUDE.md)

## Local setup

```bash
cp .env.example .env   # then fill in; `make keygen` prints crypto keys
make db-up             # Postgres 16 in Docker
make migrate
make api               # http://127.0.0.1:8000/docs
make worker            # background jobs (CV parsing, later vacancies); the only LLM caller
make bot               # needs TELEGRAM_BOT_TOKEN
make web               # http://localhost:3000
make check             # lint + tests
```

LLM calls run only through Claude Code on the owner's subscription — never set `ANTHROPIC_API_KEY`.
