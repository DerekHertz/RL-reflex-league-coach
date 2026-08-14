import { MetricFact } from "@/lib/api";
import { formatNumber, peerLabel, rankTercile, rankTercileColorVar } from "@/lib/presentation";
import styles from "./RankStrip.module.css";

const CELL_COUNT = 10;

export function RankStrip({ metric }: { metric: MetricFact }) {
  const comparison = metric.comparisons[0] ?? null;
  const rank = comparison?.rank_in_lobby ?? null;

  return (
    <div className={styles.strip}>
      <div className={styles.header}>
        <span className={`type-body ${styles.label}`}>{metric.label}</span>
        <span className={`type-data ${styles.value}`}>{formatNumber(metric.value)}</span>
      </div>
      <div className={styles.cells}>
        {Array.from({ length: CELL_COUNT }, (_, i) => {
          const position = i + 1;
          const filled = rank !== null && position === rank;
          const color = filled ? rankTercileColorVar(rankTercile(rank!, CELL_COUNT)) : "var(--paper-500)";
          return (
            <span
              key={position}
              className={styles.cell}
              style={{ background: color }}
              data-filled={filled || undefined}
            />
          );
        })}
      </div>
      <p className={`type-micro ${styles.caption}`}>
        {comparison && rank !== null
          ? `rank ${rank}/${CELL_COUNT} · ${peerLabel(comparison.peer)} ${formatNumber(comparison.peer_value)}`
          : "no peer comparison available"}
      </p>
    </div>
  );
}
