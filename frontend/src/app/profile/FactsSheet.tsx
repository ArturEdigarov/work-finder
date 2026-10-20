"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { api, errorCode } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/useErrorMessage";

import styles from "./profile.module.css";
import {
  CEFR,
  FIELDS,
  LIST_FIELDS,
  list,
  str,
  type Fact,
  type FactValue,
  type Profile,
} from "./types";

type Props = { profile: Profile | null; onProfile: (profile: Profile) => void };

const CHIP_TYPES = [
  "desired_role",
  "skill",
  "language",
  "driving_license",
] as const;
const CHIP_KEY: Record<string, string> = {
  desired_role: "name",
  skill: "name",
  language: "language",
  driving_license: "class",
};
/** Sections of a "tabellarischer Lebenslauf", in this order. */
const SECTIONS = [
  "desired_role",
  "experience",
  "education",
  "skill",
  "language",
  "certificate",
  "driving_license",
  "answer",
  "other",
] as const;

type Api = {
  save: (fact: Fact, value: FactValue) => Promise<string | null>;
  remove: (fact: Fact) => Promise<void>;
  add: (type: string, value: FactValue) => Promise<string | null>;
};

export function FactsSheet({ profile, onProfile }: Props) {
  const t = useTranslations("profile");
  const errorMessage = useErrorMessage();

  if (!profile || profile.facts.length === 0) {
    return (
      <article className={styles.sheet}>
        <p className={styles.empty}>{t("empty")}</p>
      </article>
    );
  }

  const factApi: Api = {
    async save(fact, value) {
      const { data, error } = await api.PATCH("/profile/facts/{fact_id}", {
        params: { path: { fact_id: fact.id } },
        body: { value },
      });
      if (!data) return errorMessage(errorCode(error));
      onProfile(data);
      return null;
    },
    async remove(fact) {
      const { data } = await api.DELETE("/profile/facts/{fact_id}", {
        params: { path: { fact_id: fact.id } },
      });
      if (data) onProfile(data);
    },
    async add(type, value) {
      const { data, error } = await api.POST("/profile/facts", {
        body: { type: type as never, value },
      });
      if (!data) return errorMessage(errorCode(error));
      onProfile(data);
      return null;
    },
  };

  const of = (type: string) => profile.facts.filter((f) => f.type === type);
  const head = ["personal", "profession", "location"].flatMap(of);

  return (
    <article className={styles.sheet} aria-label={t("title")}>
      {head.length > 0 && (
        <header className={styles.sheetHead}>
          {head.map((fact) => (
            <EditableFact
              key={fact.id}
              fact={fact}
              api={factApi}
              variant="head"
            />
          ))}
        </header>
      )}

      {SECTIONS.map((type) => {
        const facts = of(type);
        const isChip = (CHIP_TYPES as readonly string[]).includes(type);
        if (facts.length === 0 && !isChip) return null;
        return (
          <section
            key={type}
            className={styles.section}
            aria-labelledby={`s-${type}`}
          >
            <h3 id={`s-${type}`}>{t(`groups.${type}`)}</h3>
            {isChip ? (
              <ul className={styles.chips}>
                {facts.map((fact) => (
                  <li key={fact.id}>
                    <EditableFact fact={fact} api={factApi} variant="chip" />
                  </li>
                ))}
                <li>
                  <AddChip type={type} onAdd={factApi.add} />
                </li>
              </ul>
            ) : (
              <ul className={styles.rows}>
                {facts.map((fact) => (
                  <li key={fact.id}>
                    <EditableFact fact={fact} api={factApi} variant="row" />
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </article>
  );
}

function period(value: Fact["value"], present: string): string {
  const start = str(value.start);
  const end = str(value.end) === "present" ? present : str(value.end);
  if (start && end) return `${start} – ${end}`;
  return start || end;
}

function EditableFact({
  fact,
  api: factApi,
  variant,
}: {
  fact: Fact;
  api: Api;
  variant: "head" | "chip" | "row";
}) {
  const t = useTranslations("profile");
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const v = fact.value;
  const userMade = fact.source !== "cv";

  if (editing) {
    return (
      <FactEditor
        fact={fact}
        onCancel={() => setEditing(false)}
        onSave={async (value) => {
          const err = await factApi.save(fact, value);
          if (!err) setEditing(false);
          return err;
        }}
      />
    );
  }

  const actions = (
    <span className={styles.actions}>
      {confirming ? (
        <>
          <button
            className={styles.danger}
            onClick={() => void factApi.remove(fact)}
          >
            {t("deleteConfirm")}
          </button>
          <button onClick={() => setConfirming(false)}>{t("cancel")}</button>
        </>
      ) : (
        <>
          <button onClick={() => setEditing(true)}>{t("edit")}</button>
          <button onClick={() => setConfirming(true)}>{t("delete")}</button>
        </>
      )}
    </span>
  );

  if (variant === "chip") {
    const label = str(v[CHIP_KEY[fact.type]]);
    const level =
      fact.type === "language" ? str(v.cefr) || str(v.level_text) : "";
    return (
      <span className={styles.chip} data-user={userMade}>
        <button
          className={styles.chipLabel}
          onClick={() => setEditing(true)}
          title={t(`source.${fact.source}`)}
        >
          {label}
          {level && (
            <span className={styles.level}>
              {level === "native" ? "★" : level}
            </span>
          )}
        </button>
        <button
          className={styles.chipRemove}
          aria-label={`${t("delete")}: ${label}`}
          onClick={() => void factApi.remove(fact)}
        >
          ×
        </button>
      </span>
    );
  }

  if (variant === "head") {
    const text =
      fact.type === "personal"
        ? str(v.full_name)
        : fact.type === "profession"
          ? str(v.name)
          : [str(v.postcode), str(v.city), str(v.country)]
              .filter(Boolean)
              .join(" ");
    return (
      <div className={styles.headLine} data-type={fact.type}>
        <p>{text}</p>
        {actions}
      </div>
    );
  }

  // row: tabular Lebenslauf — dates left, content right
  const title =
    str(v.title) ||
    str(v.qualification) ||
    str(v.name) ||
    str(v.question) ||
    str(v.text);
  const where = [
    str(v.employer) || str(v.institution) || str(v.issuer),
    str(v.location),
  ]
    .filter(Boolean)
    .join(", ");
  const details = list(v.details);
  const when =
    fact.type === "certificate" ? str(v.date) : period(v, t("present"));

  return (
    <div className={styles.entry} data-user={userMade}>
      <span className={styles.when}>{when}</span>
      <div className={styles.what}>
        <p className={styles.rowTitle}>{title}</p>
        {fact.type === "answer" ? (
          <p>{str(v.text)}</p>
        ) : (
          where && <p className="hint">{where}</p>
        )}
        {details.length > 0 && (
          <ul className={styles.details}>
            {details.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        )}
        {userMade && (
          <p className={styles.source}>{t(`source.${fact.source}`)}</p>
        )}
      </div>
      {actions}
    </div>
  );
}

function FactEditor({
  fact,
  onSave,
  onCancel,
}: {
  fact: Fact;
  onSave: (value: FactValue) => Promise<string | null>;
  onCancel: () => void;
}) {
  const t = useTranslations("profile");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const fields = FIELDS[fact.type] ?? Object.keys(fact.value);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value: FactValue = {};
    // keep fields we don't edit (e.g. the question of an answer)
    for (const [k, v] of Object.entries(fact.value)) {
      if (!fields.includes(k))
        value[k] =
          typeof v === "string" || Array.isArray(v)
            ? (v as string | string[])
            : null;
    }
    for (const field of fields) {
      const raw = String(form.get(field) ?? "");
      value[field] = LIST_FIELDS.has(field)
        ? raw
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean)
        : raw.trim() || null;
    }
    setPending(true);
    const err = await onSave(value);
    setPending(false);
    setError(err);
  }

  return (
    <form className={styles.editor} onSubmit={submit}>
      {fields.map((field) => {
        const id = `${fact.id}-${field}`;
        const current = fact.value[field];
        return (
          <label key={field} className="field" htmlFor={id}>
            <span>{t(`fields.${field}` as never)}</span>
            {field === "cefr" ? (
              <select
                id={id}
                name={field}
                className="input"
                defaultValue={str(current)}
              >
                <option value="">–</option>
                {CEFR.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            ) : LIST_FIELDS.has(field) ? (
              <>
                <textarea
                  id={id}
                  name={field}
                  className="input"
                  rows={4}
                  defaultValue={list(current).join("\n")}
                />
                <span className="hint">{t("detailsHint")}</span>
              </>
            ) : (
              <input
                id={id}
                name={field}
                className="input"
                defaultValue={str(current)}
              />
            )}
          </label>
        );
      })}
      <div className={styles.row}>
        <button
          type="submit"
          className="button button-primary"
          disabled={pending}
        >
          {t("save")}
        </button>
        <button
          type="button"
          className="button button-quiet"
          onClick={onCancel}
        >
          {t("cancel")}
        </button>
      </div>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function AddChip({
  type,
  onAdd,
}: {
  type: string;
  onAdd: (type: string, value: FactValue) => Promise<string | null>;
}) {
  const t = useTranslations("profile");
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button className={styles.addChip} onClick={() => setOpen(true)}>
        + {t("add")}
      </button>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const err = await onAdd(type, { [CHIP_KEY[type]]: text.trim() });
    setError(err);
    if (!err) {
      setText("");
      setOpen(false);
    }
  }

  return (
    <form className={styles.addForm} onSubmit={submit}>
      <input
        className="input"
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t(`addPlaceholder.${type}` as never)}
        aria-label={t(`groups.${type}` as never)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      />
      <button
        type="submit"
        className="button button-primary"
        disabled={!text.trim()}
      >
        {t("add")}
      </button>
      {error && <span className="error-text">{error}</span>}
    </form>
  );
}
