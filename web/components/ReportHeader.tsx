import { MatchFactSheet } from "@/lib/api";
import { ResultBadge } from "./ResultBadge";
import styles from "./ReportHeader.module.css";

export function ReportHeader({
  sheet,
  headline,
  model,
  elapsedS,
  usedFallback,
}: {
  sheet: MatchFactSheet;
  headline: string;
  model: string;
  elapsedS: number;
  usedFallback?: boolean;
}) {
  const { subject, match, lane_opponent } = sheet;
  const eyebrowLine = [match.queue_name, `Patch ${match.patch}`, match.duration, match.team_side].join(" · ");

  return (
    <header className={styles.header}>
      <p className={`type-eyebrow ${styles.eyebrow}`}>{eyebrowLine}</p>

      <div className={styles.identity}>
        <h1 className="type-champion-name">{subject.champion}</h1>
        <span className={styles.meta}>
          {subject.role}
          {lane_opponent && <> vs {lane_opponent.champion}</>}
        </span>
        <ResultBadge result={match.result} />
      </div>

      <blockquote className={styles.headline}>
        <p className="type-quote">{headline}</p>
      </blockquote>

      <p className={`type-body-s ${styles.provenance}`}>
        {usedFallback ? `${model} attempted, didn't validate` : `Narrated by Claude · ${model}`} · {elapsedS}s
      </p>
      {usedFallback && (
        <p className={`type-body-s ${styles.fallback}`}>
          Claude&apos;s structured narration didn&apos;t validate, so this report uses a simplified
          fallback summary instead.
        </p>
      )}
    </header>
  );
}
