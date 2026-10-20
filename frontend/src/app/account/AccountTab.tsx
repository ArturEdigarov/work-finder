"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import type { Locale } from "@/i18n/config";
import { api, type User } from "@/lib/api/client";

import styles from "./account.module.css";

type Props = { user: User; onUserChange: (user: User) => void };

export function AccountTab({ user, onUserChange }: Props) {
  const t = useTranslations("account");
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const role = (["owner", "user", "admin"] as const).find(
    (r) => r === user.role,
  );

  async function saveLocale(locale: Locale) {
    const { data } = await api.PATCH("/me", { body: { locale } });
    if (data) {
      onUserChange(data);
      setSavedAt(Date.now());
    }
  }

  return (
    <>
      <div className={styles.block}>
        <dl className={styles.facts}>
          <dt>{t("email")}</dt>
          <dd>{user.email}</dd>
          <dt>{t("role")}</dt>
          <dd>{role ? t(`roles.${role}`) : user.role}</dd>
        </dl>
      </div>

      <div className={styles.block}>
        <div className={styles.row} style={{ alignItems: "end" }}>
          <div style={{ minWidth: 220 }}>
            <LocaleSwitcher onChange={saveLocale} id="locale-account" />
          </div>
          {savedAt && (
            <span key={savedAt} className={styles.saved} role="status">
              {t("languageSaved")}
            </span>
          )}
        </div>
        <p className="hint">{t("languageHint")}</p>
      </div>
    </>
  );
}
