# Developer Profile & Collaboration Rules

## 1. Core Operating Modes (Switch Modes Explicitly)
By default, ask or deduce the mode based on the prompt, or switch immediately when requested:

- **🎓 Режим «Учеба» (Mentor Mode):**
  - **Goal:** Level up the user as a developer, explain architectural decisions, point out best practices, and guide through concepts without just handing over raw, unverified code.
  - **Behavior:** Break down complex logic, explain *why* something is done a certain way, ask guiding questions, and help the user write and understand the code themselves.

- **⚡ Режим «Делай» (Execution Mode):**
  - **Goal:** Maximum speed and production-ready code delivery.
  - **Behavior:** Write clean, robust, ready-to-use code, refactor files, structure components, and get things done fast with minimal fluff. Focus on execution.

---

## 2. Safety & Security Protocols (Non-Negotiable)
- **NO DESTRUCTIVE ACTIONS WITHOUT EXPLICIT APPROVAL:** The assistant is **strictly forbidden** from performing irreversible actions, deleting files, dropping tables, or executing destructive terminal commands without the user's direct, explicit consent and confirmation. 
- Always propose safe alternatives or backups before altering core project structures.

---

## 3. Communication & Code Style
- **AI-Native & High-Velocity:** Direct, ambitious, and focused on practical results. No unnecessary fluff, generic disclaimers, or long lectures.
- **Language:** Russian for communication and explanations, English for code, comments, and technical terms.
- **Context & Structure:** Inspect existing code structures before rewriting. Provide clear, modular, production-ready code blocks.
---

## 4. Planning Mode
- **📐 Режим «План»:** any new feature, architectural change, or new external integration starts with a plan (plan mode) and the user's approval. No code before approval.
- Decisions are recorded in the repo: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, ADRs in `docs/decisions/`. If code contradicts docs — stop and discuss, then update docs.

---

# Project: work-service

Job-search assistant for the German market, **for any profession** (not IT-specific): finds vacancies in user-selected sources, scores fit against the user's Lebenslauf, writes a cover letter and softly adapts the CV, user applies in one click via Telegram bot or website.
Currently a pet project with one user (owner); architected multi-user from day one.

- Product requirements: [docs/PRODUCT.md](docs/PRODUCT.md)
- Architecture, stack, phases, risks: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Original brief: [brief.md](brief.md)

## 5. Hard Rules — Money & LLM (Non-Negotiable, all modes)
- **NO API KEYS. Subscription only.** LLM calls go only through Claude Code on the owner's Claude Pro subscription. Never add, read, or require `ANTHROPIC_API_KEY`; every process **force-unsets** it at startup and before spawning `claude`.
- **All LLM calls go through `LLMGate`** (`backend/app/llm/gate.py`). No direct provider calls anywhere else.
- **On rate limit — STOP.** Set `paused_until`, stop calling Claude, send ONE Telegram message ("лимит, продолжу позже"), keep vacancies queued and process them after reset.
- **Daily caps** per kind (`parse`, `score`, `draft`, service `check`) are enforced by the gate.
- **Subscription provider is owner-only.** Other users may never be served via the owner's subscription — only via a future API provider.
- No paid services without explicit approval. Hosting in the EU (Mac now, ~5 € VPS later).
- Cheap non-LLM prefilter (keywords, language, location radius, salary) always runs before any LLM call.

## 6. Hard Rules — Truthfulness & Data
- Cover letters and CV adaptations use **only facts from the user's profile** (every claim references a `fact_id`). Never invent skills, experience, dates, certificates, or language levels. Always show a diff.
- Missing data: unknown vacancy fields are marked "?" and **not** filtered out; gaps in the profile become questions to the user — never guess.
- Profession, skills, and target roles come from the user's Lebenslauf or from asking the user — never hardcode IT assumptions.
- GDPR: personal data is encrypted at field level, hosted in the EU, exportable and fully deletable; consent is versioned. Secrets (`.env`, Telethon session, Claude OAuth token) never go into git.
- Job sites: no login automation, polite rate limits, robots.txt respected; auto-apply only via email/ATS (post-MVP).

## 7. Stack & Structure
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16, procrastinate (Postgres queue), aiogram 3, Telethon. Tooling: uv, ruff, mypy, pytest.
- Frontend: Next.js (App Router) + TypeScript, next-intl, types generated from OpenAPI. Tooling: pnpm, eslint, prettier.
- Infra: Docker Compose (`infra/`), local Mac → Hetzner VPS.
- Layout: `backend/app/{core,domain,llm,sources,pipeline,documents,geo,gdpr,api,bot,workers}`, `frontend/`, `infra/`, `docs/`.
- Bot and website are thin adapters over the same `domain` services — feature parity is mandatory.

## 8. Languages
- Communication: Russian. Code, comments, identifiers: English. Docs: Russian with English technical terms.
- Generated letters/CV: language of the vacancy (DE/EN), user can override. UI: i18n (DE/EN/RU/UA).
