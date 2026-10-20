"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import {
  isLocale,
  localeNames,
  locales,
  setLocaleCookie,
  type Locale,
} from "@/i18n/config";

type Props = {
  /** Extra side effect, e.g. saving the locale to the account. */
  onChange?: (locale: Locale) => Promise<void>;
  /** Hide the visible label (header usage). */
  compact?: boolean;
  id?: string;
};

export function LocaleSwitcher({ onChange, compact, id = "locale" }: Props) {
  const t = useTranslations("common");
  const current = useLocale();
  const router = useRouter();

  async function change(value: string) {
    if (!isLocale(value)) return;
    setLocaleCookie(value);
    await onChange?.(value);
    router.refresh();
  }

  return (
    <label className={compact ? undefined : "field"} htmlFor={id}>
      <span className={compact ? "visually-hidden" : undefined}>
        {t("language")}
      </span>
      <select
        id={id}
        className="input"
        style={compact ? { width: "auto", padding: "7px 10px" } : undefined}
        value={current}
        onChange={(e) => void change(e.target.value)}
      >
        {locales.map((locale) => (
          <option key={locale} value={locale}>
            {localeNames[locale]}
          </option>
        ))}
      </select>
    </label>
  );
}
