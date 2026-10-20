"use client";

import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { isLocale } from "@/i18n/config";
import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./register.module.css";

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
    if (!data) {
      setPending(false);
      setError(errorMessage(errorCode(error)));
      return;
    }
    router.replace("/account");
    router.refresh();
  }

  return (
    <AuthShell
      title={t("registerTitle")}
      lead={t("registerLead")}
      footer={
        <>
          {t("toLogin")} <Link href="/login">{t("toLoginLink")}</Link>
        </>
      }
    >
      <form onSubmit={submit} className="field" style={{ gap: 16 }}>
        <label className="field">
          <span>{t("email")}</span>
          <input
            name="email"
            type="email"
            className="input"
            autoComplete="email"
            required
          />
        </label>
        <PasswordField
          label={t("password")}
          autoComplete="new-password"
          minLength={PASSWORD_MIN_LENGTH}
        />
        <label className={styles.consent}>
          <input
            name="consent"
            type="checkbox"
            required
            disabled={!consentVersion}
          />
          <span>{t("consent", { version: consentVersion ?? "…" })}</span>
        </label>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="button button-primary"
          disabled={pending || !consentVersion}
        >
          {pending ? t("pending") : t("submitRegister")}
        </button>
      </form>
    </AuthShell>
  );
}
