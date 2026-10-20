"""Bot messages. Locale comes from the linked account, else from Telegram's language_code."""

TEXTS: dict[str, dict[str, str]] = {
    "profile_ready": {
        "ru": "✅ Профиль готов: {facts} фактов из твоего Lebenslauf. Проверить и поправить можно на сайте во вкладке «Профиль».",
        "uk": "✅ Профіль готовий: {facts} фактів із твого Lebenslauf. Перевірити й виправити можна на сайті у вкладці «Профіль».",
        "de": "✅ Profil fertig: {facts} Fakten aus deinem Lebenslauf. Prüfen und korrigieren kannst du sie auf der Website unter „Profil“.",
        "en": "✅ Profile ready: {facts} facts from your CV. You can review and fix them on the website under “Profile”.",
    },
    "questions_intro": {
        "ru": "Пара вопросов, чтобы точнее подбирать вакансии (осталось: {count}). Отвечай обычным сообщением.",
        "uk": "Кілька питань, щоб точніше підбирати вакансії (залишилось: {count}). Відповідай звичайним повідомленням.",
        "de": "Ein paar Fragen, damit die Stellen besser passen (offen: {count}). Antworte einfach mit einer Nachricht.",
        "en": "A few questions so the jobs fit better ({count} left). Just reply with a message.",
    },
    "question": {
        "ru": "❓ {question}",
        "uk": "❓ {question}",
        "de": "❓ {question}",
        "en": "❓ {question}",
    },
    "skip_button": {"ru": "Пропустить", "uk": "Пропустити", "de": "Überspringen", "en": "Skip"},
    "answer_saved": {
        "ru": "Сохранил ✅",
        "uk": "Зберіг ✅",
        "de": "Gespeichert ✅",
        "en": "Saved ✅",
    },
    "skipped": {"ru": "Пропущено.", "uk": "Пропущено.", "de": "Übersprungen.", "en": "Skipped."},
    "all_answered": {
        "ru": "Вопросов больше нет 🎉 Профиль можно посмотреть на сайте.",
        "uk": "Питань більше немає 🎉 Профіль можна переглянути на сайті.",
        "de": "Keine offenen Fragen mehr 🎉 Dein Profil findest du auf der Website.",
        "en": "No more questions 🎉 Your profile is on the website.",
    },
    "no_questions": {
        "ru": "Открытых вопросов нет. Когда появятся вакансии, они придут сюда.",
        "uk": "Відкритих питань немає. Коли з'являться вакансії, вони прийдуть сюди.",
        "de": "Keine offenen Fragen. Passende Stellen kommen hierher, sobald es sie gibt.",
        "en": "No open questions. Matching jobs will arrive here once there are any.",
    },
    "no_profile": {
        "ru": "Профиля ещё нет. Загрузи Lebenslauf на сайте, и я задам пару вопросов.",
        "uk": "Профілю ще немає. Завантаж Lebenslauf на сайті, і я поставлю кілька питань.",
        "de": "Noch kein Profil. Lade deinen Lebenslauf auf der Website hoch, dann frage ich nach.",
        "en": "No profile yet. Upload your CV on the website and I'll ask a few questions.",
    },
    "not_linked": {
        "ru": "Этот чат не привязан. Открой сайт → Аккаунт → Telegram → «Создать ссылку».",
        "uk": "Цей чат не прив'язано. Відкрий сайт → Акаунт → Telegram → «Створити посилання».",
        "de": "Dieser Chat ist nicht verknüpft. Website → Konto → Telegram → „Link erstellen“.",
        "en": "This chat isn't linked. Website → Account → Telegram → “Create link”.",
    },
    "llm_rate_limited": {
        "ru": "⏸ Лимит Claude исчерпан, продолжу позже (примерно в {until}). Вакансии копятся в очереди.",
        "uk": "⏸ Ліміт Claude вичерпано, продовжу пізніше (приблизно о {until}). Вакансії накопичуються в черзі.",
        "de": "⏸ Claude-Limit erreicht, ich mache später weiter (ca. {until}). Stellen werden in der Warteschlange gesammelt.",
        "en": "⏸ Claude limit reached, I'll continue later (around {until}). Vacancies are queued.",
    },
    "llm_auth_error": {
        "ru": "⚠️ Claude Code не авторизован (истёк вход или токен). Выполни `claude /login` (на VPS — `claude setup-token`). До этого вызовы на паузе.",
        "uk": "⚠️ Claude Code не авторизований (сплив вхід або токен). Виконай `claude /login` (на VPS — `claude setup-token`). До того виклики на паузі.",
        "de": "⚠️ Claude Code ist nicht angemeldet (Login oder Token abgelaufen). Führe `claude /login` aus (auf dem VPS `claude setup-token`). Bis dahin sind Aufrufe pausiert.",
        "en": "⚠️ Claude Code is not authenticated (login or token expired). Run `claude /login` (on the VPS: `claude setup-token`). Calls are paused until then.",
    },
    "linked": {
        "ru": "✅ Аккаунт привязан. Сюда будут приходить вакансии и уведомления.",
        "uk": "✅ Акаунт прив'язано. Сюди надходитимуть вакансії та сповіщення.",
        "de": "✅ Konto verknüpft. Stellenangebote und Benachrichtigungen kommen hierher.",
        "en": "✅ Account linked. Vacancies and notifications will arrive here.",
    },
    "link_invalid": {
        "ru": "Ссылка недействительна или устарела. Создай новую в настройках аккаунта на сайте.",
        "uk": "Посилання недійсне або застаріле. Створи нове в налаштуваннях акаунта на сайті.",
        "de": "Der Link ist ungültig oder abgelaufen. Erstelle einen neuen in den Kontoeinstellungen.",
        "en": "This link is invalid or expired. Create a new one in your account settings.",
    },
    "chat_taken": {
        "ru": "Этот Telegram уже привязан к другому аккаунту.",
        "uk": "Цей Telegram вже прив'язаний до іншого акаунта.",
        "de": "Dieses Telegram ist bereits mit einem anderen Konto verknüpft.",
        "en": "This Telegram is already linked to another account.",
    },
    "start_no_token": {
        "ru": "Привет! Чтобы привязать бота, открой сайт → Аккаунт → «Привязать Telegram».",
        "uk": "Привіт! Щоб прив'язати бота, відкрий сайт → Акаунт → «Прив'язати Telegram».",
        "de": "Hallo! Zum Verknüpfen öffne die Website → Konto → „Telegram verknüpfen“.",
        "en": "Hi! To link this bot, open the website → Account → “Link Telegram”.",
    },
}


def t(key: str, locale: str | None, **params: object) -> str:
    variants = TEXTS[key]
    lang = (locale or "en").split("-")[0]
    text = variants.get(lang, variants["en"])
    return text.format(**params) if params else text
