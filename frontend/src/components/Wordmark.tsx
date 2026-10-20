import Link from "next/link";

import styles from "./Wordmark.module.css";

/** Folder-register tab + name. */
export function Wordmark() {
  return (
    <Link href="/account" className={styles.wordmark}>
      <svg viewBox="0 0 28 22" width="28" height="22" aria-hidden="true">
        <path d="M1 5.5A2.5 2.5 0 0 1 3.5 3H10l2.5 3H24.5A2.5 2.5 0 0 1 27 8.5v10A2.5 2.5 0 0 1 24.5 21h-21A2.5 2.5 0 0 1 1 18.5Z" />
      </svg>
      work-finder
    </Link>
  );
}
