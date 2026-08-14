import { SkillScore } from "@/lib/api";
import { SkillBandRow } from "./SkillBandRow";
import styles from "./SkillBandList.module.css";

export const SKILL_BAND_CAPTION =
  "Only a handful of skill categories have a detector behind them so far, and this version " +
  "never claims a band outperforms the lobby -- it only flags falling short or holding steady.";

export function SkillBandList({ scores }: { scores: SkillScore[] }) {
  if (scores.length === 0) return null;
  return (
    <div className={styles.list}>
      <div className={styles.rows}>
        {scores.map((score) => (
          <SkillBandRow key={score.skill} score={score} />
        ))}
      </div>
      <p className={`type-body-s ${styles.caption}`}>{SKILL_BAND_CAPTION}</p>
    </div>
  );
}
