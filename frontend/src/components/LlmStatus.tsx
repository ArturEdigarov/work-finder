"use client";

import { useFormatter, useTranslations } from "next-intl";

import styles from "@/app/account/account.module.css";
import type { components } from "@/lib/api/schema";

export type LlmStatusData = components["schemas"]["LlmStatusOut"];

/**
 * PRODUCT §4.8: LLM limits are visible to the user.
 * Each kind is a stamp card: one cell per allowed call today.
 */
export function LlmStatus({ status }: { status: LlmStatusData | null }) {
  const t = useTranslations("llm");
  const format = useFormatter();

  if (!status) return null;

  if (!status.available) {
    return (
      <div className={styles.block}>
        <h2>{t("title")}</h2>
        <span className={styles.pill} data-state="unavailable">
          {t("unavailable")}
        </span>
      </div>
    );
  }

  const until = status.paused_until
    ? format.dateTime(new Date(status.paused_until), {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <>
      <div className={styles.block}>
        <h2>{t("title")}</h2>
        <span className={styles.pill} data-state={until ? "paused" : "ready"}>
          {until ? t("paused", { until }) : t("ready")}
        </span>
        {until && <p>{t("pausedText")}</p>}
      </div>

      <div className={styles.block}>
        <p className="hint">{t("today")}</p>
        <ul className={styles.meters}>
          {status.usage.map((u) => (
            <li
              key={u.kind}
              className={u.used >= u.cap ? styles.meterFull : undefined}
            >
              <div className={styles.meterHead}>
                <span>{t(`kinds.${u.kind}`)}</span>
                <span>{t("usage", { used: u.used, cap: u.cap })}</span>
              </div>
              <div
                className={styles.cells}
                role="meter"
                aria-label={t(`kinds.${u.kind}`)}
                aria-valuemin={0}
                aria-valuemax={u.cap}
                aria-valuenow={u.used}
              >
                {Array.from({ length: u.cap }, (_, i) => (
                  <span
                    key={i}
                    className={styles.cell}
                    data-used={i < u.used}
                  />
                ))}
              </div>
            </li>
          ))}
        </ul>
        <p className="hint">{t("note")}</p>
      </div>
    </>
  );
}
