"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { LlmStatus } from "@/components/LlmStatus";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { isLocale, setLocaleCookie, type Locale } from "@/i18n/config";
import { api, errorCode, type User } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

export default function AccountPage() {
  const t = useTranslations("account");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [telegramLink, setTelegramLink] = useState<{
    url: string;
    minutes: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.GET("/me").then(({ data, response }) => {
      if (response.status === 401) {
        router.replace("/login");
        return;
      }
      if (data) {
        setUser(data);
        // The account's language wins over the browser default.
        if (
          isLocale(data.locale) &&
          !document.cookie.includes(`NEXT_LOCALE=${data.locale}`)
        ) {
          setLocaleCookie(data.locale);
          router.refresh();
        }
      }
    });
  }, [router]);

  if (!user) return <p>{tc("loading")}</p>;

  async function saveLocale(locale: Locale) {
    const { data } = await api.PATCH("/me", { body: { locale } });
    if (data) setUser(data);
  }

  async function createTelegramLink() {
    setError(null);
    const { data, error } = await api.POST("/me/telegram-link");
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    setTelegramLink({ url: data.url, minutes: data.expires_in_minutes });
  }

  async function unlinkTelegram() {
    await api.DELETE("/me/telegram-link");
    setUser((u) => (u ? { ...u, telegram_linked: false } : u));
  }

  async function logout() {
    await api.POST("/auth/logout");
    router.replace("/login");
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm(t("deleteConfirm"))) return;
    const password = String(new FormData(event.currentTarget).get("password"));
    setError(null);
    const { error, response } = await api.POST("/me/delete", {
      body: { password },
    });
    if (!response.ok) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    router.replace("/register");
  }

  return (
    <>
      <div className="row">
        <h1>{t("title")}</h1>
        <button onClick={() => void logout()}>{tc("logout")}</button>
      </div>

      <section>
        <p>
          {t("email")}: <strong>{user.email}</strong>
          <br />
          {t("role")}: {user.role}
        </p>
        <LocaleSwitcher onChange={saveLocale} />
      </section>

      <section>
        <h2>{t("telegramTitle")}</h2>
        {user.telegram_linked ? (
          <div className="row">
            <span>{t("telegramLinked")}</span>
            <button onClick={() => void unlinkTelegram()}>
              {t("telegramUnlink")}
            </button>
          </div>
        ) : (
          <>
            <p className="hint">{t("telegramNotLinked")}</p>
            {telegramLink ? (
              <p>
                <a
                  href={telegramLink.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {telegramLink.url}
                </a>
                <br />
                <span className="hint">
                  {t("telegramLinkHint", { minutes: telegramLink.minutes })}
                </span>
              </p>
            ) : (
              <button onClick={() => void createTelegramLink()}>
                {t("telegramLink")}
              </button>
            )}
          </>
        )}
      </section>

      <LlmStatus />

      {error && <p className="error">{error}</p>}

      <section>
        <h2>{t("dataTitle")}</h2>
        {/* Same-origin via the /api rewrite, so the session cookie is sent. */}
        <a href="/api/me/export" download>
          {t("export")}
        </a>
        <form onSubmit={deleteAccount}>
          <h3>{t("deleteTitle")}</h3>
          <p className="hint">{t("deleteHint")}</p>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          <button type="submit" className="error">
            {t("delete")}
          </button>
        </form>
      </section>
    </>
  );
}
