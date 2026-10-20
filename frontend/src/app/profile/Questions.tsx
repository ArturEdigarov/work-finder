"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./profile.module.css";
import type { Profile, Question } from "./types";

type Props = { profile: Profile; onProfile: (profile: Profile) => void };

export function Questions({ profile, onProfile }: Props) {
  const t = useTranslations("profile");
  const open = profile.questions.filter((q) => q.status === "open");
  if (open.length === 0) return null;

  return (
    <section
      className={`${styles.card} ${styles.questions}`}
      aria-labelledby="q-title"
    >
      <h2 id="q-title">
        {t("questionsTitle")}{" "}
        <span className={styles.count}>{open.length}</span>
      </h2>
      <p className="hint">{t("questionsLead")}</p>
      <ul className={styles.qList}>
        {open.map((q) => (
          <QuestionItem key={q.id} question={q} onProfile={onProfile} />
        ))}
      </ul>
    </section>
  );
}

function QuestionItem({
  question,
  onProfile,
}: {
  question: Question;
  onProfile: (profile: Profile) => void;
}) {
  const t = useTranslations("profile");
  const errorMessage = useErrorMessage();
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = { params: { path: { question_id: question.id } } };

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const { data, error } = await api.POST(
      "/profile/questions/{question_id}/answer",
      {
        ...path,
        body: { text },
      },
    );
    setPending(false);
    if (!data) {
      setError(errorMessage(errorCode(error)));
      return;
    }
    onProfile(data);
  }

  async function skip() {
    const { data } = await api.POST(
      "/profile/questions/{question_id}/dismiss",
      path,
    );
    if (data) onProfile(data);
  }

  return (
    <li>
      <form className={styles.qItem} onSubmit={submit}>
        <label htmlFor={`a-${question.id}`} className={styles.qText}>
          {question.question}
        </label>
        <textarea
          id={`a-${question.id}`}
          className="input"
          rows={2}
          maxLength={2000}
          placeholder={t("answerPlaceholder")}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className={styles.row}>
          <button
            type="submit"
            className="button button-primary"
            disabled={pending || !text.trim()}
          >
            {t("answer")}
          </button>
          <button
            type="button"
            className="button button-quiet"
            onClick={() => void skip()}
          >
            {t("skip")}
          </button>
        </div>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
      </form>
    </li>
  );
}
