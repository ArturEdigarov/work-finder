import { useTranslations } from "next-intl";

/** Maps a backend error code (see app/domain/accounts.py) to a localized message. */
export function useErrorMessage(): (code: string) => string {
  const t = useTranslations("errors");
  return (code) => (t.has(code) ? t(code) : t("unknown_error"));
}
