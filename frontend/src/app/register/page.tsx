"use client";

import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { isLocale } from "@/i18n/config";
import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

// Must match `password_min_length` in backend/app/core/config.py.
const PASSWORD_MIN_LENGTH = 12;

export default function RegisterPage() {
  const t = useTranslations("auth");
  const errorMessage = useErrorMessage();
  const locale = useLocale();
  const router = useRouter();
  const [consentVersion, setConsentVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    void api
      .GET("/auth/consent")
      .then(({ data }) => setConsentVersion(data?.version ?? null));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!consentVersion) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const { data, error } = await api.POST("/auth/register", {
      body: {
        email: String(form.get("email")),
        password: String(form.get("password")),
        consent_version: consentVersion,
        locale: isLocale(locale) ? locale : "de",
      },
    });
    setPending(false);
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    router.replace("/account");
    router.refresh();
  }

  return (
    <>
      <div className="row">
        <h1>{t("registerTitle")}</h1>
        <LocaleSwitcher />
      </div>
      <form onSubmit={submit}>
        <label>
          {t("email")}
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label>
          {t("password")}
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={PASSWORD_MIN_LENGTH}
            required
          />
          <span className="hint">
            {t("passwordHint", { min: PASSWORD_MIN_LENGTH })}
          </span>
        </label>
        <label className="checkbox">
          <input
            name="consent"
            type="checkbox"
            required
            disabled={!consentVersion}
          />
          <span>{t("consent", { version: consentVersion ?? "…" })}</span>
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={pending || !consentVersion}>
          {t("submitRegister")}
        </button>
        <Link href="/login">{t("toLogin")}</Link>
      </form>
    </>
  );
}
