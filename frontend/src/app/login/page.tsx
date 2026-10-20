"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
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
    setPending(false);
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    if (isLocale(data.locale)) setLocaleCookie(data.locale);
    router.replace("/account");
    router.refresh();
  }

  return (
    <>
      <div className="row">
        <h1>{t("loginTitle")}</h1>
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
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={pending}>
          {t("submitLogin")}
        </button>
        <Link href="/register">{t("toRegister")}</Link>
      </form>
    </>
  );
}
