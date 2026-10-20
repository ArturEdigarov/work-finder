import { useTranslations } from "next-intl";

import styles from "./HeroSheet.module.css";

/**
 * The product in one picture: a real-looking German job ad on an A4 sheet. On load the
 * highlighter marks what the CV covers, the missing requirement gets a note, then the
 * match stamp lands. Reduced motion shows the final state.
 * The ad itself stays German in every UI language — vacancies are German.
 */
export function HeroSheet() {
  const t = useTranslations("hero");

  return (
    <figure className={styles.desk} aria-label={t("sheetLabel")} role="img">
      <div className={styles.cv} aria-hidden="true">
        <span className={styles.cvName}>Lebenslauf</span>
        {Array.from({ length: 9 }, (_, i) => (
          <span
            key={i}
            className={styles.cvLine}
            style={{ width: `${55 + ((i * 37) % 40)}%` }}
          />
        ))}
      </div>

      <article className={styles.sheet} aria-hidden="true">
        <p className={styles.company}>Hafenküche GmbH, Hamburg-Altona</p>
        <p className={styles.title}>Koch / Köchin (m/w/d)</p>
        <p className={styles.terms}>
          Vollzeit, ab sofort, 3.100–3.400 € brutto
        </p>

        <p className={styles.section}>Das bringst du mit</p>
        <ul className={styles.list}>
          <li>
            <mark
              className={styles.mark}
              style={{ "--i": 0 } as React.CSSProperties}
            >
              Abgeschlossene Ausbildung als Koch/Köchin
            </mark>
          </li>
          <li>
            <mark
              className={styles.mark}
              style={{ "--i": 1 } as React.CSSProperties}
            >
              Erfahrung in der À-la-carte-Küche
            </mark>
          </li>
          <li className={styles.gap}>
            <span className={styles.gapText}>Führerschein Klasse B</span>
            <span className={styles.gapNote}>{t("gap")}</span>
          </li>
          <li>
            <mark
              className={styles.mark}
              style={{ "--i": 2 } as React.CSSProperties}
            >
              Deutschkenntnisse mindestens B2
            </mark>
          </li>
        </ul>

        <div className={styles.stamp}>
          <span className={styles.pct} />
          <span className={styles.stampLabel}>{t("stamp")}</span>
        </div>
      </article>
    </figure>
  );
}
