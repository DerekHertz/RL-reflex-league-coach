import { SkillScore } from "@/lib/api";
import { bandColorVar, bandLabel } from "@/lib/presentation";
import styles from "./SkillBandRow.module.css";

export function SkillBandRow({ score }: { score: SkillScore }) {
  return (
    <div className={styles.row}>
      <span className={`type-body ${styles.skill}`}>{score.skill}</span>
      <span className={styles.band} style={{ color: bandColorVar(score.band) }}>
        {bandLabel(score.band)}
      </span>
    </div>
  );
}
