"use client";

import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import styles from "./PasswordField.module.css";

type Props = {
  name?: string;
  label: string;
  autoComplete: "current-password" | "new-password";
  /** Shows a length meter towards this minimum (registration). */
  minLength?: number;
};

export function PasswordField({
  name = "password",
  label,
  autoComplete,
  minLength,
}: Props) {
  const t = useTranslations("auth");
  const id = useId();
  const [visible, setVisible] = useState(false);
  const [length, setLength] = useState(0);
  const remaining = minLength ? Math.max(0, minLength - length) : 0;

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className={styles.wrap}>
        <input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          className="input"
          autoComplete={autoComplete}
          minLength={minLength}
          required
          aria-describedby={minLength ? `${id}-meter` : undefined}
          onChange={(e) => setLength(e.target.value.length)}
        />
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? t("hidePassword") : t("showPassword")}
          aria-pressed={visible}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
            <circle cx="12" cy="12" r="3" />
            {visible && <path d="M4 4l16 16" />}
          </svg>
        </button>
      </div>
      {minLength && (
        <div id={`${id}-meter`} className={styles.meter} aria-live="polite">
          <span
            className={styles.bar}
            data-ok={remaining === 0}
            style={
              {
                "--fill": Math.min(1, length / minLength),
              } as React.CSSProperties
            }
          />
          <span className={remaining === 0 ? styles.ok : "hint"}>
            {remaining === 0
              ? t("passwordOk")
              : t("passwordRemaining", { count: remaining })}
          </span>
        </div>
      )}
    </div>
  );
}
