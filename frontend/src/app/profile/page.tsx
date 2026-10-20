"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { api } from "@/lib/api/client";

import { CvCard } from "./CvCard";
import { FactsSheet } from "./FactsSheet";
import { Questions } from "./Questions";
import styles from "./profile.module.css";
import type { CvDocument, Profile } from "./types";

const POLL_MS = 3000;

export default function ProfilePage() {
  const t = useTranslations("profile");
  const tc = useTranslations("common");
  const router = useRouter();
  const [loaded, setLoaded] = useState(false);
  const [cv, setCv] = useState<CvDocument | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  const refreshProfile = useCallback(async () => {
    const { data } = await api.GET("/profile");
    setProfile(data ?? null);
  }, []);

  useEffect(() => {
    void (async () => {
      const me = await api.GET("/me");
      if (me.response.status === 401) {
        router.replace("/login");
        return;
      }
      const [doc, prof] = await Promise.all([
        api.GET("/documents/cv"),
        api.GET("/profile"),
      ]);
      setCv(doc.data ?? null);
      setProfile(prof.data ?? null);
      setLoaded(true);
    })();
  }, [router]);

  // While Claude works on the CV, poll until the parse finishes.
  const working = profile?.status === "queued" || profile?.status === "parsing";
  useEffect(() => {
    if (!working) return;
    const id = setInterval(() => void refreshProfile(), POLL_MS);
    return () => clearInterval(id);
  }, [working, refreshProfile]);

  if (!loaded) {
    return (
      <div className={styles.page}>
        <p className="hint">{tc("loading")}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.heading}>
        <h1>{t("title")}</h1>
        <p>{t("lead")}</p>
      </div>

      <div className={styles.layout}>
        <aside className={styles.aside}>
          <CvCard
            cv={cv}
            profile={profile}
            onUploaded={(doc) => {
              setCv(doc);
              void refreshProfile();
            }}
            onProfile={setProfile}
          />
          {profile && <Questions profile={profile} onProfile={setProfile} />}
        </aside>
        <main className={styles.main}>
          <FactsSheet profile={profile} onProfile={setProfile} />
        </main>
      </div>
    </div>
  );
}
