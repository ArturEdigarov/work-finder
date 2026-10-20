"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthShell } from "@/components/AuthShell";
import { PasswordField } from "@/components/PasswordField";
import { isLocale, setLocaleCookie } from "@/i18n/config";
import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

export default function LoginPage() {
  const t = useTranslations("auth");
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const { data, error } = await api.POST("/auth/login", {
      body: {
        email: String(form.get("email")),
        password: String(form.get("password")),
      },
    });
    if (!data) {
      setPending(false);
      setError(errorMessage(errorCode(error)));
      return;
    }
    if (isLocale(data.locale)) setLocaleCookie(data.locale);
    router.replace("/profile");
    router.refresh();
  }

  return (
    <AuthShell
      title={t("loginTitle")}
      lead={t("loginLead")}
      footer={
        <>
          {t("toRegister")} <Link href="/register">{t("toRegisterLink")}</Link>
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
        <PasswordField label={t("password")} autoComplete="current-password" />
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="button button-primary"
          disabled={pending}
        >
          {pending ? t("pending") : t("submitLogin")}
        </button>
      </form>
    </AuthShell>
  );
}
