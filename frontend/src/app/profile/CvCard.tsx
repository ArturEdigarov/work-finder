"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useId, useState, type DragEvent } from "react";

import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./profile.module.css";
import type { CvDocument, Profile } from "./types";

type Props = {
  cv: CvDocument | null;
  profile: Profile | null;
  onUploaded: (doc: CvDocument) => void;
  onProfile: (profile: Profile) => void;
};

export function CvCard({ cv, profile, onUploaded, onProfile }: Props) {
  const t = useTranslations("profile");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    // multipart: plain fetch through the same-origin /api proxy (session cookie is sent)
    const resp = await fetch("/api/documents/cv", { method: "POST", body });
    const data: unknown = await resp.json().catch(() => null);
    setUploading(false);
    if (!resp.ok) {
      setError(errorMessage(errorCode(data)));
      return;
    }
    onUploaded(data as CvDocument);
  }

  async function reparse() {
    setError(null);
    const { data, error } = await api.POST("/profile/parse");
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    onProfile(data);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files[0]);
  }

  const date = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "medium" });

  const dropzone = (compact: boolean) => (
    <label
      htmlFor={inputId}
      className={styles.drop}
      data-compact={compact}
      data-dragging={dragging}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <input
        id={inputId}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="visually-hidden"
        disabled={uploading}
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {uploading ? (
        <span>{t("uploading")}</span>
      ) : compact ? (
        <span>{t("replace")}</span>
      ) : (
        <>
          <svg viewBox="0 0 40 48" width="40" height="48" aria-hidden="true">
            <path d="M4 2h22l10 10v32a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" />
            <path d="M26 2v10h10M20 36V20m-7 7 7-7 7 7" />
          </svg>
          <strong>{t("dropTitle")}</strong>
          <span>
            {t("dropOr")} <span className={styles.fakeLink}>{t("choose")}</span>
          </span>
          <span className="hint">{t("dropHint")}</span>
        </>
      )}
    </label>
  );

  return (
    <section className={styles.card} aria-labelledby="cv-title">
      <h2 id="cv-title">{t("cvTitle")}</h2>

      {!cv ? (
        dropzone(false)
      ) : (
        <>
          <div className={styles.file}>
            <span className={styles.fileIcon} aria-hidden="true">
              {cv.content_type.includes("pdf") ? "PDF" : "DOCX"}
            </span>
            <div>
              <p className={styles.fileName}>{cv.filename}</p>
              <p className="hint">
                {t("uploadedAt", { date: date(cv.created_at) })},{" "}
                {Math.max(1, Math.round(cv.size_bytes / 1024))} KB
              </p>
            </div>
          </div>

          {cv.status === "no_text" ? (
            <p className={styles.warn}>{t("noText")}</p>
          ) : (
            profile && (
              <div
                className={styles.status}
                data-status={profile.status}
                role="status"
              >
                {(profile.status === "queued" ||
                  profile.status === "parsing") && (
                  <>
                    <p className={styles.working}>
                      <span className={styles.pulse} aria-hidden="true" />
                      {t(`status.${profile.status}`)}
                    </p>
                    <p className="hint">{t("statusHint")}</p>
                  </>
                )}
                {profile.status === "ready" && profile.parsed_at && (
                  <p className="hint">
                    {t("status.ready", { date: date(profile.parsed_at) })}
                  </p>
                )}
                {profile.status === "failed" && (
                  <>
                    <p className={styles.warn}>{t("status.failed")}</p>
                    <div>
                      <button
                        className="button button-quiet"
                        onClick={() => void reparse()}
                      >
                        {t("retry")}
                      </button>
                    </div>
                  </>
                )}
                {profile.status === "unavailable" && (
                  <p className="hint">{t("status.unavailable")}</p>
                )}
              </div>
            )
          )}
          {dropzone(true)}
        </>
      )}

      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
