import { formatAxisPercent } from "@/lib/presentation";
import styles from "./PlaystyleBar.module.css";

/** A single playstyle axis as a labeled horizontal fill bar. Distinct from
 * RankStrip: that component encodes a discrete "rank n/10 in this lobby"
 * position; this one is a continuous 0..1 score with no lobby-rank meaning,
 * so it's a plain proportional fill rather than a 10-cell strip. */
export function PlaystyleBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={styles.row}>
      <div className={styles.header}>
        <span className={`type-body ${styles.label}`}>{label}</span>
        <span className={`type-data ${styles.value}`}>{formatAxisPercent(value)}</span>
      </div>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
