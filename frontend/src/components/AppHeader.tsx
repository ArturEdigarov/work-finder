"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api/client";

import { Wordmark } from "./Wordmark";
import styles from "./AppHeader.module.css";

const LINKS = [
  { href: "/profile", key: "profile" },
  { href: "/account", key: "account" },
] as const;

export function AppHeader() {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await api.POST("/auth/logout");
    router.replace("/login");
  }

  return (
    <header className={styles.header}>
      <Wordmark />
      <nav aria-label={t("label")} className={styles.nav}>
        {LINKS.map(({ href, key }) => (
          <Link
            key={href}
            href={href}
            className={styles.link}
            aria-current={pathname === href ? "page" : undefined}
          >
            {t(key)}
          </Link>
        ))}
      </nav>
      <button className="button button-quiet" onClick={() => void logout()}>
        {tc("logout")}
      </button>
    </header>
  );
}
