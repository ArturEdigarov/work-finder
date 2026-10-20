"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Status = components["schemas"]["LlmStatusOut"];

/** PRODUCT §4.8: LLM limits are visible to the user. */
export function LlmStatus() {
  const t = useTranslations("llm");
  const format = useFormatter();
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    void api.GET("/llm/status").then(({ data }) => setStatus(data ?? null));
  }, []);

  if (!status) return null;

  return (
    <section>
      <h2>{t("title")}</h2>
      {!status.available ? (
        <p className="hint">{t("unavailable")}</p>
      ) : status.paused_until ? (
        <p className="error">
          {t("paused", {
            until: format.dateTime(new Date(status.paused_until), {
              day: "2-digit",
              month: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            }),
          })}
        </p>
      ) : (
        <p>{t("active")}</p>
      )}
      {status.available && (
        <>
          <span className="hint">{t("today")}</span>
          <ul>
            {status.usage.map((u) => (
              <li key={u.kind}>
                {t(`kinds.${u.kind}`)}: {u.used} / {u.cap}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
