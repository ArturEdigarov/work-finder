// Must match `Locale` in backend/app/api/schemas.py.
export const locales = ["de", "en", "ru", "uk"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "de";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export const localeNames: Record<Locale, string> = {
  de: "Deutsch",
  en: "English",
  ru: "Русский",
  uk: "Українська",
};

export function isLocale(value: string | undefined): value is Locale {
  return locales.includes(value as Locale);
}

/** Client-side: remember the UI language; the server reads it in i18n/request.ts. */
export function setLocaleCookie(locale: Locale): void {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; samesite=lax`;
}
