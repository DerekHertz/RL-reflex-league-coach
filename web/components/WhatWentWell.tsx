import styles from "./WhatWentWell.module.css";

export function WhatWentWell({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className={styles.section}>
      <p className={`type-eyebrow ${styles.eyebrow}`}>What went well</p>
      <ul className={styles.list}>
        {items.map((item, i) => (
          <li key={i} className={styles.item}>
            <span className={styles.bullet} aria-hidden="true">
              ✦
            </span>
            <span className="type-body">{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
