"use client";

import { useEffect, useState } from "react";
import { fetchMeta } from "@/lib/api";
import styles from "./Disclaimer.module.css";

/** Always fetched live from GET /api/meta -- never hardcoded, so the text
 * stays correct if the backend changes it. */
export function Disclaimer() {
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMeta()
      .then((meta) => {
        if (!cancelled) setText(meta.disclaimer);
      })
      .catch(() => {
        // Non-critical: if /api/meta is unreachable, omit the footer rather
        // than showing a stale or fabricated disclaimer.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!text) return null;

  return (
    <footer className={styles.footer}>
      <p className={styles.text}>{text}</p>
    </footer>
  );
}
