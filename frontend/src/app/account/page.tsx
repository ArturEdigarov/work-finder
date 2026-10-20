"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { LlmStatus, type LlmStatusData } from "@/components/LlmStatus";
import { Wordmark } from "@/components/Wordmark";
import { isLocale, setLocaleCookie } from "@/i18n/config";
import { api, type User } from "@/lib/api/client";

import { AccountTab } from "./AccountTab";
import { DataTab } from "./DataTab";
import { TelegramTab } from "./TelegramTab";
import styles from "./account.module.css";

const TABS = ["account", "telegram", "llm", "data"] as const;
type Tab = (typeof TABS)[number];

function tabFromHash(): Tab {
  const hash = window.location.hash.slice(1);
  return (TABS as readonly string[]).includes(hash) ? (hash as Tab) : "account";
}

export default function AccountPage() {
  const t = useTranslations("account");
  const tc = useTranslations("common");
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [llm, setLlm] = useState<LlmStatusData | null>(null);
  // Tabs render only after /me loads, so reading the hash here cannot cause a hydration mismatch.
  const [tab, setTab] = useState<Tab>(() =>
    typeof window === "undefined" ? "account" : tabFromHash(),
  );
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({
    account: null,
    telegram: null,
    llm: null,
    data: null,
  });

  useEffect(() => {
    void api.GET("/me").then(({ data, response }) => {
      if (response.status === 401) {
        router.replace("/login");
        return;
      }
      if (!data) return;
      setUser(data);
      // The account's language wins over the browser default.
      if (
        isLocale(data.locale) &&
        !document.cookie.includes(`NEXT_LOCALE=${data.locale}`)
      ) {
        setLocaleCookie(data.locale);
        router.refresh();
      }
    });
    void api.GET("/llm/status").then(({ data }) => setLlm(data ?? null));
  }, [router]);

  // Links to /account#telegram etc. switch the tab without a reload.
  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const select = useCallback((next: Tab, focus = false) => {
    setTab(next);
    window.history.replaceState(null, "", `#${next}`);
    if (focus) tabRefs.current[next]?.focus();
  }, []);

  function onTabKey(event: KeyboardEvent) {
    const i = TABS.indexOf(tab);
    const moves: Record<string, number> = {
      ArrowRight: (i + 1) % TABS.length,
      ArrowLeft: (i - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    };
    if (event.key in moves) {
      event.preventDefault();
      select(TABS[moves[event.key]], true);
    }
  }

  async function logout() {
    await api.POST("/auth/logout");
    router.replace("/login");
  }

  if (!user) {
    return (
      <div className={styles.page}>
        <p className="hint">{tc("loading")}</p>
      </div>
    );
  }

  const attention: Partial<Record<Tab, "ink" | "danger">> = {
    telegram: user.telegram_linked ? undefined : "ink",
    llm: llm?.paused_until ? "danger" : undefined,
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <Wordmark />
        <button className="button button-quiet" onClick={() => void logout()}>
          {tc("logout")}
        </button>
      </header>

      <div className={styles.heading}>
        <h1>{t("title")}</h1>
        <p>{user.email}</p>
      </div>

      <div
        role="tablist"
        aria-label={t("tabsLabel")}
        className={styles.tabs}
        onKeyDown={onTabKey}
      >
        {TABS.map((name) => (
          <button
            key={name}
            ref={(el) => {
              tabRefs.current[name] = el;
            }}
            role="tab"
            id={`tab-${name}`}
            aria-selected={tab === name}
            aria-controls={`panel-${name}`}
            tabIndex={tab === name ? 0 : -1}
            className={styles.tab}
            data-attention={attention[name]}
            onClick={() => select(name)}
          >
            {t(`tabs.${name}`)}
          </button>
        ))}
      </div>

      <section
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
        className={styles.panel}
      >
        {tab === "account" && <AccountTab user={user} onUserChange={setUser} />}
        {tab === "telegram" && (
          <TelegramTab user={user} onUserChange={setUser} />
        )}
        {tab === "llm" && <LlmStatus status={llm} />}
        {tab === "data" && <DataTab />}
      </section>
    </div>
  );
}
