"""Bot messages. Locale comes from the linked account, else from Telegram's language_code."""

TEXTS: dict[str, dict[str, str]] = {
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


def t(key: str, locale: str | None, **params: str) -> str:
    variants = TEXTS[key]
    lang = (locale or "en").split("-")[0]
    text = variants.get(lang, variants["en"])
    return text.format(**params) if params else text
