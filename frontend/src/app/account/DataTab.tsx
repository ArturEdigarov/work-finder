"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PasswordField } from "@/components/PasswordField";
import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./account.module.css";

export function DataTab() {
  const t = useTranslations("data");
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Two steps: the first submit only asks "are you sure?".
    if (!confirming) {
      setConfirming(true);
      return;
    }
    const password = String(new FormData(event.currentTarget).get("password"));
    setPending(true);
    setError(null);
    const { error, response } = await api.POST("/me/delete", {
      body: { password },
    });
    if (!response.ok) {
      setPending(false);
      setConfirming(false);
      setError(errorMessage(errorCode(error)));
      return;
    }
    router.replace("/register");
  }

  return (
    <>
      <div className={styles.block}>
        <h2>{t("exportTitle")}</h2>
        <p>{t("exportText")}</p>
        <div>
          {/* Same-origin via the /api rewrite, so the session cookie is sent. */}
          <a className="button button-quiet" href="/api/me/export" download>
            {t("exportButton")}
          </a>
        </div>
      </div>

      <form className={`${styles.block} ${styles.danger}`} onSubmit={submit}>
        <h2>{t("deleteTitle")}</h2>
        <p>{t("deleteText")}</p>
        <div style={{ maxWidth: 340 }}>
          <PasswordField
            label={t("deletePassword")}
            autoComplete="current-password"
          />
        </div>
        {confirming ? (
          <div
            className={styles.confirm}
            role="alertdialog"
            aria-label={t("deleteAsk")}
          >
            <strong>{t("deleteAsk")}</strong>
            <div className={styles.row}>
              <button
                type="submit"
                className="button button-danger"
                disabled={pending}
                autoFocus
              >
                {t("deleteConfirm")}
              </button>
              <button
                type="button"
                className="button button-quiet"
                onClick={() => setConfirming(false)}
              >
                {t("deleteCancel")}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <button type="submit" className="button button-quiet">
              {t("deleteButton")}
            </button>
          </div>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
      </form>
    </>
  );
}
