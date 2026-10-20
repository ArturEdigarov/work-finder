import { useTranslations } from "next-intl";

import { HeroSheet } from "./HeroSheet";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { Wordmark } from "./Wordmark";
import styles from "./AuthShell.module.css";

type Props = {
  title: string;
  lead: string;
  children: React.ReactNode;
  footer: React.ReactNode;
};

/** Login/register frame: the product promise on the left, the form sheet on the right. */
export function AuthShell({ title, lead, children, footer }: Props) {
  const t = useTranslations("hero");

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Wordmark />
        <LocaleSwitcher compact id="locale-header" />
      </header>

      <div className={styles.grid}>
        <section className={styles.promise}>
          <h1 className={styles.headline}>{t("title")}</h1>
          <p className={styles.lead}>{t("lead")}</p>
        </section>

        <div className={styles.desk}>
          <HeroSheet />
        </div>

        <main className={styles.formSheet}>
          <h2 className={styles.formTitle}>{title}</h2>
          <p className="hint">{lead}</p>
          {children}
          <p className={styles.switch}>{footer}</p>
        </main>
      </div>
    </div>
  );
}
