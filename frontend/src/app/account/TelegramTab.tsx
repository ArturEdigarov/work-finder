"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { api, errorCode, type User } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./account.module.css";

type Props = { user: User; onUserChange: (user: User) => void };
type Link = { url: string; expiresAt: number };

const POLL_MS = 3000;

function formatLeft(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function TelegramTab({ user, onUserChange }: Props) {
  const t = useTranslations("telegram");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const [link, setLink] = useState<Link | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [copied, setCopied] = useState(false);
  const [justLinked, setJustLinked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = link !== null && now < link.expiresAt && !user.telegram_linked;
  const expired =
    link !== null && now >= link.expiresAt && !user.telegram_linked;

  // While the link is valid: tick the countdown and watch for the bot confirming /start.
  useEffect(() => {
    if (!active) return;
    const tick = setInterval(() => setNow(Date.now()), 1000);
    const poll = setInterval(() => {
      void api.GET("/me").then(({ data }) => {
        if (data?.telegram_linked) {
          setJustLinked(true);
          setLink(null);
          onUserChange(data);
        }
      });
    }, POLL_MS);
    return () => {
      clearInterval(tick);
      clearInterval(poll);
    };
  }, [active, onUserChange]);

  async function createLink() {
    setError(null);
    const { data, error } = await api.POST("/me/telegram-link");
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    setNow(Date.now());
    setLink({
      url: data.url,
      expiresAt: Date.now() + data.expires_in_minutes * 60_000,
    });
  }

  async function copy() {
    if (!link) return;
    await navigator.clipboard.writeText(link.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function unlink() {
    await api.DELETE("/me/telegram-link");
    setJustLinked(false);
    onUserChange({ ...user, telegram_linked: false });
  }

  if (user.telegram_linked) {
    return (
      <div className={styles.block}>
        <div className={styles.connected} role="status">
          <span className={styles.check}>
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path
                d="M5 12.5l4.5 4.5L19 7.5"
                style={justLinked ? undefined : { animation: "none" }}
              />
            </svg>
          </span>
          <h2>{t("success")}</h2>
        </div>
        <p>{t("linked")}</p>
        <div>
          <button className="button button-quiet" onClick={() => void unlink()}>
            {t("unlink")}
          </button>
        </div>
      </div>
    );
  }

  const stepState = (step: 1 | 2 | 3) => {
    if (!active) return step === 1 ? "current" : "todo";
    return step === 1 ? "done" : "current";
  };

  return (
    <div className={styles.block}>
      <p>{t("intro")}</p>
      <ol className={styles.steps}>
        <li data-state={stepState(1)}>{t("step1")}</li>
        <li data-state={stepState(2)}>{t("step2")}</li>
        <li data-state={stepState(3)}>{t("step3")}</li>
      </ol>

      {active && link ? (
        <div className={styles.linkBox}>
          <div className={styles.row}>
            <a
              className="button button-primary"
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("open")}
            </a>
            <button className="button button-quiet" onClick={() => void copy()}>
              {copied ? tc("copied") : tc("copy")}
            </button>
          </div>
          <div className={styles.waiting} role="status">
            <span className={styles.pulse} aria-hidden="true" />
            <span>{t("waiting")}</span>
          </div>
          <p className="hint">
            {t("expiresIn", { time: formatLeft(link.expiresAt - now) })}
          </p>
        </div>
      ) : (
        <div className={styles.row}>
          <button
            className="button button-primary"
            onClick={() => void createLink()}
          >
            {t("create")}
          </button>
          {expired && <span className="hint">{t("expired")}</span>}
        </div>
      )}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
