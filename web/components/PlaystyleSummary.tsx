import { PlaystyleVector } from "@/lib/api";
import { axisLabel, isLowConfidence, LOW_CONFIDENCE_CAVEAT, sampleSizeCaption } from "@/lib/presentation";
import { PlaystyleBar } from "./PlaystyleBar";
import styles from "./PlaystyleSummary.module.css";

const AXIS_KEYS = [
  "aggression",
  "farming",
  "vision",
  "objective_focus",
  "risk_tolerance",
  "teamfight_vs_split",
] as const;

export function PlaystyleSummary({ playstyle }: { playstyle: PlaystyleVector }) {
  return (
    <section className={styles.section}>
      <p className={`type-eyebrow ${styles.eyebrow}`}>Playstyle</p>
      <div className={styles.bars}>
        {AXIS_KEYS.map((key) => (
          <PlaystyleBar key={key} label={axisLabel(key)} value={playstyle[key]} />
        ))}
      </div>
      <p className={`type-micro ${styles.caption}`}>
        {sampleSizeCaption(playstyle.sample_size)}
        {isLowConfidence(playstyle.confidence) ? ` -- ${LOW_CONFIDENCE_CAVEAT}` : ""}
      </p>
    </section>
  );
}
