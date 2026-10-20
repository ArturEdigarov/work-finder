# ARCHITECTURE — work-service

> Статус: согласовано 2026-10-18. Продуктовые требования — в [PRODUCT.md](PRODUCT.md). Существенные решения дополнительно фиксируются как ADR в `docs/decisions/`.

## 1. Стек

| Слой | Технология | Почему |
|---|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2 | типизированные схемы → OpenAPI → TS-типы для фронта |
| БД | PostgreSQL 16, SQLAlchemy 2 (async) + Alembic | одна БД для данных, очереди и состояния лимитов |
| Очередь / шедулер | procrastinate (очередь на Postgres) | без Redis: меньше сервисов и памяти на 5 € VPS |
| Telegram-бот | aiogram 3 | зрелый async-фреймворк |
| Чтение каналов | Telethon (user-аккаунт, отдельный номер) | стабильнее аналогов на JS |
| Парсинг сайтов | httpx + selectolax; Playwright только при необходимости | минимум ресурсов |
| Разбор документов | pdfplumber, python-docx | PDF/DOCX Lebenslauf |
| Генерация документов | WeasyPrint + HTML/Jinja2-шаблоны | письмо по DIN 5008, CV в PDF |
| Гео | офлайн-справочник PLZ/городов DE (GeoNames) + haversine | радиус без платных API |
| Язык текста | lingua-py | офлайн-определение языка |
| LLM | `LLMProvider` → `ClaudeCodeSubscriptionProvider` (сейчас), `AnthropicApiProvider` (позже) | см. §5 |
| Frontend | Next.js (App Router) + TypeScript, openapi-typescript + openapi-fetch, next-intl | типизированный клиент API из OpenAPI |
| Инструменты | uv, ruff, mypy, pytest (Python); pnpm, eslint, prettier (TS) | |
| Инфра | Docker Compose; Mac → VPS Hetzner (ЕС) | одинаковое окружение |

## 2. Структура репозитория

```
work-service/
  CLAUDE.md
  README.md
  brief.md
  docs/
    PRODUCT.md
    ARCHITECTURE.md
    decisions/            # ADR: 0001-llm-subscription-only.md, ...
  backend/
    pyproject.toml
    app/
      core/               # config, logging, security, crypto (field encryption), i18n
      domain/             # сущности и сервисы — единый слой для API и бота
      llm/
        provider.py       # LLMProvider protocol, LLMRequest/LLMResult, ошибки
        claude_code.py    # ClaudeCodeSubscriptionProvider
        anthropic_api.py  # AnthropicApiProvider (позже)
        fake.py           # для тестов
        gate.py           # LLMGate: потолки, пауза, owner-only, уведомление
        prompts/          # шаблоны + JSON-схемы ответов
      sources/
        base.py           # JobSource protocol
        manual.py  telegram.py  bundesagentur.py  stepstone.py  indeed.py  ...
      pipeline/           # normalize, dedupe, prefilter, score, draft
      documents/          # cv_parse, render_pdf, diff, truth_validator
      geo/
      gdpr/               # consent, export, delete, retention
      api/                # FastAPI routers
      bot/                # aiogram handlers, keyboards
      workers/            # procrastinate tasks + periodic schedules
    migrations/
    tests/
  frontend/               # Next.js
  infra/
    docker-compose.yml
    postgres/init/        # создание тестовой БД
  .github/workflows/      # CI: ruff, mypy, pytest (+ frontend lint/typecheck)
  .env.example            # шаблон .env (сам .env — вне git)
  Makefile
```

## 3. Процессы (контейнеры)

| Процесс | Ответственность |
|---|---|
| `api` | FastAPI: REST для сайта, auth, загрузки файлов |
| `worker` | procrastinate: задачи конвейера, расписания источников, Telethon-reader, LLM-вызовы через `LLMGate` |
| `bot` | aiogram: уведомления, карточки, кнопки, ручная вставка вакансий |
| `frontend` | Next.js |
| `postgres` | данные, очередь, состояние лимитов |

`claude` CLI устанавливается в образ `worker` (единственный процесс, который вызывает LLM).

## 4. Модель данных (основные сущности)

| Сущность | Ключевые поля |
|---|---|
| `User` | id, email, password_hash, role (owner/user/admin), locale, telegram_chat_id, llm_provider |
| `Consent` | user_id, version, accepted_at, revoked_at |
| `Document` | user_id, kind (cv/certificate/…), file (encrypted), parsed_text (encrypted) |
| `Profile` | user_id, structured JSON (опыт, образование, навыки, языки, локация, роли) — encrypted; версии |
| `ProfileFact` | profile_id, fact_id, type, value, source (cv / user_answer) — то, на что ссылаются письма |
| `ProfileQuestion` | user_id, question, status, answer → становится `ProfileFact` |
| `SearchSettings` | user_id, roles/keywords, exclude, location (lat/lon), radius_km, remote, languages, min_salary |
| `Source` | kind (telegram/site/manual), config, global или user-defined, health, last_polled_at |
| `UserSource` | user_id, source_id, enabled |
| `Vacancy` | общий пул: source_id, external_id, url, title, company, location, geo, salary, language, text, content_hash, posted_at |
| `Match` | user_id, vacancy_id, status, prefilter_result, keyword_score, chance_pct, explanation, matches, gaps, missing_info |
| `ApplicationPackage` | match_id, letter, cv_variant, diff, language, pdf files, apply_url / mailto |
| `LlmUsage` | user_id, kind (parse/score/draft), date, count |
| `LlmState` | provider, paused_until, notified_at |
| `AuditLog` | user_id, action, at (для GDPR и отладки) |

Статусы `Match`:
```
new → filtered_out
    → queued → scored → notified → drafting → ready → applied
                                 ↘ skipped (из любого состояния после scored)
```

## 5. LLM-слой

### 5.1 `LLMProvider`
```python
class LLMProvider(Protocol):
    name: str
    async def complete(self, req: LLMRequest) -> LLMResult: ...
```
`LLMRequest`: kind (`parse` | `score` | `draft`), prompt, JSON-схема ответа, user_id.
Ошибки: `LLMRateLimited(reset_at | None)`, `LLMAuthError`, `LLMInvalidOutput`.

### 5.2 `ClaudeCodeSubscriptionProvider`
- Вызывает `claude -p --output-format json --json-schema <schema> --model <alias> --tools "" --no-session-persistence --strict-mcp-config --setting-sources ""` как subprocess с **очищенным env** (`sanitized_env()`): `ANTHROPIC_API_KEY` удаляется всегда, переменные родительской сессии Claude Code (`CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, …) тоже; `CLAUDE_CODE_OAUTH_TOKEN` сохраняется.
- **`--bare` запрещён:** в этом режиме CLI авторизуется только через `ANTHROPIC_API_KEY`.
- cwd — новый пустой temp-каталог (не подхватываются `CLAUDE.md` и настройки проекта); промпт — через **stdin** (персональные данные не попадают в argv / `ps`); одновременно один вызов.
- Ответ: результат по схеме — поле `structured_output` (fallback — JSON в `result`); ошибки — `is_error`, `api_error_status` (429 → лимит, 401/403 → авторизация), текст в `result`. Время сброса лимита парсится из текста (`|<epoch>` или `resets 3pm (Europe/Berlin)`), иначе — backoff гейта.
- Аутентификация: локально — логин Claude Code владельца; на VPS — `CLAUDE_CODE_OAUTH_TOKEN` из `claude setup-token`. Есть сообщения об ошибках 401 и об отсутствии автообновления токена → healthcheck + уведомление admin.
- Распознаёт сообщения о лимите → `LLMRateLimited`.
- Валидирует ответ по JSON-схеме; при невалидном ответе — одна повторная попытка, далее `LLMInvalidOutput`.

### 5.3 `LLMGate` (единственная точка входа к LLM)
1. **Owner-only:** провайдер с `subscription=True` обслуживает только `role=owner` (admin ≠ owner). Иначе `LLMForbidden`, вызова нет.
2. **Пауза:** если `LlmState.paused_until > now` → `LLMDeferred(retry_at=paused_until, "paused")`, вызова нет.
3. **Дневные потолки** (`LLM_DAILY_CAP_*`, день — по `Europe/Berlin`): слот резервируется **до** вызова одним атомарным `INSERT … ON CONFLICT DO UPDATE … WHERE count < cap` — параллельные вызовы не превышают потолок. Превышение → `LLMDeferred(до полуночи, "daily_cap")`. Потолок 0 — вид вызова выключен.
4. **Вызов провайдера** — без открытой транзакции БД.
5. **Учёт слота:** успех и `LLMInvalidOutput` — слот израсходован (модель отработала); лимит, ошибка авторизации, временный сбой — слот возвращается.
6. **Лимит подписки / ошибка авторизации** → пауза (`reset_at` из ответа, иначе backoff 60 → 120 → 240 → 300 мин), `SELECT … FOR UPDATE` по `LlmState`; **ровно одно** сообщение admin в Telegram на эпизод (`notified_at`); тексты `llm_rate_limited` / `llm_auth_error`. Сбой отправки не отменяет паузу. `LLMDeferred` → вызывающий (воркер, фаза 3) переставляет задачу на `retry_at`.
7. **Конец эпизода:** первый успешный вызов сбрасывает `pause_streak`, `notified_at`, `paused_until`.
8. Лог каждого вызова: user_id, kind, prompt_version, модель, длительность, токены — без текста промпта.

При старте любого процесса: если `ANTHROPIC_API_KEY` есть в окружении — warning в лог и `unset`.

### 5.4 Промпты
Пакет `llm/prompts/`: каждый промпт — модуль с константой `PROMPT = Prompt(name, version, kind, system, template, output)`.
- `template` — `string.Template` (`$name`), безопасен для JSON-скобок в тексте; незаполненный плейсхолдер → `KeyError`, полупустой промпт не отправляется.
- `output` — Pydantic-модель; её JSON-схема уходит в `--json-schema`, ответ валидируется ею же.
- `prompt_version = name@version` логируется с каждым вызовом; при изменении текста или модели — повышать `version`.
- Оценка вернёт `chance_pct`, `explanation`, `matches[]`, `gaps[]`, `missing_info[]`; письма/CV — `fact_ids` на каждое утверждение (фазы 4, 6).

Виды вызовов: `parse`, `score`, `draft` + служебный `check` (`make llm-check`, потолок 3/день, не трогает слоты оценок).

### 5.5 Наблюдаемость
- `GET /llm/status` — для текущего пользователя: доступен ли провайдер, `paused_until`, расход за сегодня по видам и потолки. Показывается на странице аккаунта (PRODUCT §4.8).
- `make llm-check` — один реальный вызов `healthcheck@v1` через гейт от имени owner (exit 0 ok / 1 сбой или пауза / 2 не настроено). На VPS — периодический healthcheck токена.

## 6. Конвейер вакансий

```
ingest (source) → normalize → dedupe → prefilter → [queue] → score (LLM) → notify (bot + web)
                                                                       ↓ action "apply"
                                                    draft (LLM) → truth_validator → diff → PDF
```

- **Normalize:** единая схема `Vacancy`, геокодирование локации по офлайн-справочнику, определение языка.
- **Dedupe:** по `(source, external_id)`, url и `content_hash(company, title, location)`.
- **Prefilter (без LLM):** ключевые слова, исключения, язык, расстояние, зарплата. Неизвестные поля = «?», не причина отсева.
- **Keyword-score:** дешёвая оценка без LLM — для приоритизации очереди, когда лимит ограничен.
- **Score:** через `LLMGate`, результат в `Match`.
- **Draft:** письмо (DIN 5008) + варианты CV как операции над профилем (reorder / rephrase / emphasize / omit). `truth_validator` отклоняет утверждения без `fact_id` и новые навыки/опыт. Пользователь видит diff.

## 7. Источники

```python
class JobSource(Protocol):
    kind: str
    async def fetch(self, query: SourceQuery) -> list[RawVacancy]: ...
```
`SourceQuery`: keywords, location, radius_km, since. Telegram-источники игнорируют локацию (фильтр — в prefilter).

Правила для каждого плагина: собственный rate limit, экспоненциальный бэкофф, соблюдение robots.txt, без логина, честный User-Agent, `health` в `Source`, при поломке — уведомление admin.

| Источник | Способ | Риск |
|---|---|---|
| Ручная вставка | URL (fetch + extraction) или текст | нет |
| Telegram-каналы | Telethon, опрос раз в N минут, только публичные | ограничение аккаунта при агрессивном опросе |
| Bundesagentur für Arbeit | неофициальный REST (`rest.arbeitsagentur.de/jobboerse/jobsuche-service`), `wo` + радиус (параметр проверить на живом запросе) | низкий; API неофициальный, может измениться |
| StepStone, Indeed | HTML-парсинг | ToS запрещают скрапинг, антибот, частые изменения вёрстки |
| Arbeitnow, Adzuna и др. | публичные API / free tier | низкий |

## 8. Бот и сайт

Оба — тонкие адаптеры над `domain`-сервисами. Действия `apply`, `edit`, `skip` реализованы один раз в `domain`; состояние общее. Бот хранит связь сообщение → `match_id`, чтобы карточки обновлялись при действии на сайте.

**Сайт ↔ API.** Next проксирует `/api/*` на FastAPI (`rewrites` в `next.config.ts`, `API_URL`), поэтому сайт и API — один origin: httpOnly-cookie сессии работает без CORS. Типы клиента генерируются `make gen-types` → `frontend/src/lib/api/schema.ts` (коммитится, чтобы CI не зависел от бэкенда; после изменения API — перегенерировать).

**i18n сайта.** next-intl без префикса языка в URL: язык — cookie `NEXT_LOCALE` → `Accept-Language` → `de`. При входе cookie выставляется из `User.locale`, смена языка в аккаунте сохраняется в профиль. Тексты — `frontend/messages/{de,en,ru,uk}.json`, коды ошибок бэкенда переводятся в `errors.*`.

**Визуальная система «Bewerbungsmappe».** Образы из мира соискателя в Германии: лист A4, текстовыделитель на совпадениях, чернильный штамп с процентом, регистры папки Leitz как вкладки.
- Токены — `frontend/src/app/globals.css` (`--paper`, `--sheet`, `--graphite`, `--ink` королевский синий, `--marker` жёлтый, `--danger`, `--ok`; тёмная тема через `prefers-color-scheme`). Шрифты — Fira Sans / Fira Sans Extra Condensed (кириллица для RU/UK).
- Единственная «громкая» анимация — `HeroSheet` на входе/регистрации (маркер → пробел → штамп); `prefers-reduced-motion` показывает финальное состояние. Остальное движение — только в ответ на действия (подтверждения, Telegram-связка).
- Тексты — от лица пользователя, кнопки называют действие; ошибки объясняют, что сделать.
- Превью-сборка рядом с `pnpm dev`: `NEXT_DIST_DIR=.next-preview pnpm build && NEXT_DIST_DIR=.next-preview pnpm start -p 3100` (не ломает `.next` dev-сервера).

## 9. Безопасность и GDPR

- Field-level шифрование (AES-GCM) для контактов, резюме, профиля, документов; ключ — в env, не в репозитории.
- Пароли — argon2. Сессии — httpOnly cookie.
- Секреты (`.env`, Telethon session, OAuth-токен Claude) — вне git, права 600.
- Экспорт данных пользователя (JSON + файлы) и hard delete каскадом (БД + файлы + сгенерированные PDF).
- Retention: вакансии и логи удаляются по сроку (конфиг).
- Бэкапы Postgres — зашифрованные, хранятся в ЕС.

## 10. Деплой

1. **Основной режим сейчас — локально на Mac (localhost).**
   - Postgres в Docker; `api`, `worker`, `bot`, `frontend` можно запускать нативно (uv / pnpm) — `worker` использует обычный логин Claude Code владельца, `setup-token` не нужен.
   - Бот работает через **long polling** — публичный URL, домен и TLS не нужны.
   - Всё слушает только `127.0.0.1`.
   - Ограничение: пока Mac спит или выключен, сканирование и бот стоят. После пробуждения расписания догоняют (источники опрашиваются с `since = last_polled_at`), очередь оценок продолжается. По желанию — `caffeinate` во время работы.
2. **VPS Hetzner (ЕС) — позже, когда понадобится 24/7:** тот же compose, Caddy (TLS), `CLAUDE_CODE_OAUTH_TOKEN`, cron-бэкапы, healthchecks. Код не меняется — только конфиг.

## 11. Фазы

| # | Фаза | Сложность | Результат |
|---|---|---|---|
| 0 | Фундамент: репо, compose, Postgres, миграции, auth, согласия, шифрование, CI | M | пустой работающий каркас |
| 1 | LLM-слой: провайдеры, `LLMGate`, fake-провайдер, промпты | M | безопасные вызовы Claude с лимитами |
| 2 | Профиль: загрузка CV, разбор, правка, вопросы по пробелам | M | структурированный профиль |
| 3 | Источники: ручная вставка, Telegram, Bundesagentur, StepStone, Indeed; normalize/dedupe/geo | L | поток вакансий |
| 4 | Префильтр + оценка | M | `Match` с шансом и объяснением |
| 5 | Бот и сайт: карточки, кнопки, настройки | L | основные флоу |
| 6 | Пакет отклика: письмо, адаптация CV, diff, PDF | M–L | отклик в один клик |
| 7 | VPS + харднинг + GDPR end-to-end | M | работает 24/7 в ЕС |

После MVP — см. [PRODUCT.md §6](PRODUCT.md#6-после-mvp).

## 12. Риски

| Риск | Митигирование |
|---|---|
| Лимиты Claude Pro (окно ~5 ч + недельный) — главный ограничитель | префильтр без LLM, дневные потолки, очередь, keyword-приоритизация |
| ToS подписки: автоматизация для других пользователей запрещена | owner-only в `LLMGate`, для других — API-провайдер |
| Парсинг StepStone/Indeed: ToS, антибот, поломки; юр. риск при коммерческом запуске (§87b UrhG) | низкая частота, изоляция плагинов, health-мониторинг, приоритет официальным/бесплатным API; пересмотр перед открытием сервиса |
| Telethon: ограничение аккаунта | отдельный номер, редкий опрос, только публичные каналы |
| `setup-token` на VPS: 401, нет автообновления | healthcheck, уведомление admin, документированная процедура обновления |
| Качество разбора разных форматов резюме | обязательная ручная правка профиля |
| GDPR при открытии другим | DPA с LLM-провайдером, Impressum, Datenschutzerklärung, процедура удаления |
| Бот и сайт рассинхронизируются | единый `domain`-слой, единое состояние `Match` |
