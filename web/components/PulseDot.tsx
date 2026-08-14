import styles from "./PulseDot.module.css";

/** A small gold status pulse. Animates opacity .35 -> .9 on a 2s loop;
 * sits static (gold, no animation) under prefers-reduced-motion. */
export function PulseDot() {
  return <span className={styles.dot} aria-hidden="true" />;
}
