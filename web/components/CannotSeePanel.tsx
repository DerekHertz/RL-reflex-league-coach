"use client";

import { useState } from "react";
import styles from "./CannotSeePanel.module.css";

const COLLAPSED_COUNT = 4;

export function CannotSeePanel({ items }: { items: string[] }) {
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) return null;

  const shown = expanded ? items : items.slice(0, COLLAPSED_COUNT);
  const hasMore = items.length > COLLAPSED_COUNT;

  return (
    <section className={styles.panel}>
      <p className={`type-eyebrow ${styles.eyebrow}`}>What I cannot see</p>
      <ul className={styles.list}>
        {shown.map((item) => (
          <li key={item} className={styles.item}>
            <span className={styles.dash} aria-hidden="true">
              —
            </span>
            <span className={`type-body-s ${styles.text}`}>{item}</span>
          </li>
        ))}
      </ul>
      {hasMore && (
        <button type="button" className={styles.toggle} onClick={() => setExpanded((v) => !v)}>
          {expanded ? `${items.length} of ${items.length} · show fewer` : `${shown.length} of ${items.length} · show all`}
        </button>
      )}
    </section>
  );
}
