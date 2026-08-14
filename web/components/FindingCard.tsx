import { FindingFact, FindingNarration } from "@/lib/api";
import {
  findingHeadTintOpacity,
  formatEvidenceValue,
  formatNumber,
  formatTimestamps,
  severityColorVar,
} from "@/lib/presentation";
import { DetectorChip } from "./DetectorChip";
import { SeverityBadge } from "./SeverityBadge";
import styles from "./FindingCard.module.css";

export function FindingCard({
  finding,
  narration,
}: {
  finding: FindingFact;
  narration: FindingNarration | null;
}) {
  const color = severityColorVar(finding.severity);
  const headTintPct = Math.round(findingHeadTintOpacity(finding.severity) * 100);
  const phaseLabel = finding.phase.replace(/_/g, " ").toUpperCase();

  const evidenceItems: { label: string; value: string }[] = finding.evidence.map((e) => ({
    label: e.label,
    value: formatEvidenceValue(e.value, e.unit),
  }));
  const timestampValue = formatTimestamps(finding.timestamps);
  if (timestampValue) {
    evidenceItems.push({ label: "Timestamps", value: timestampValue });
  }

  return (
    <article className={styles.card}>
      <header
        className={styles.head}
        style={
          {
            "--head-color": color,
            "--head-tint-pct": `${headTintPct}%`,
          } as React.CSSProperties
        }
      >
        <h3 className={`type-title-m ${styles.title}`}>{finding.title}</h3>
        <div className={styles.headRight}>
          <span className={`type-micro ${styles.meta}`}>
            {phaseLabel} · conf {formatNumber(finding.confidence)}
          </span>
          <SeverityBadge severity={finding.severity} />
        </div>
      </header>
      <div className={styles.body}>
        <DetectorChip id={finding.id} severity={finding.severity} />
        <p className={`type-body ${styles.paragraph}`}>{finding.what_happened}</p>
        {narration && (
          <p className={`type-body ${styles.paragraph}`}>
            <span className="run-in-label">Fix: </span>
            {narration.fix}
          </p>
        )}
        {narration?.drill && (
          <p className={`type-body ${styles.paragraph}`}>
            <span className="run-in-label">Drill: </span>
            {narration.drill}
          </p>
        )}
        {evidenceItems.length > 0 && (
          <div className={styles.evidence}>
            {evidenceItems.map((item) => (
              <span key={item.label} className={`type-data-s ${styles.evidenceItem}`}>
                {item.label}: <span className={styles.evidenceValue}>{item.value}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
