import { ChampionRec } from "@/lib/api";
import { axisLabel, formatAxisPercent } from "@/lib/presentation";
import styles from "./ChampionRecCard.module.css";

export function ChampionRecCard({ rec }: { rec: ChampionRec }) {
  return (
    <article className={styles.card}>
      <header className={styles.head}>
        <h3 className={`type-title-m ${styles.name}`}>{rec.champion}</h3>
        <span className={`type-data-s ${styles.fitScore}`}>{formatAxisPercent(rec.fit_score)} fit</span>
      </header>
      <div className={styles.body}>
        <div className={styles.roles}>
          {rec.roles.map((role) => (
            <span key={role} className={`type-data-s ${styles.roleTag}`}>
              {role}
            </span>
          ))}
        </div>
        {rec.kind === "stretch" && rec.stretch_axis && (
          <p className={`type-body-s ${styles.stretchLine}`}>
            <span className="run-in-label">Stretch pick: </span>
            grows your {axisLabel(rec.stretch_axis)}
          </p>
        )}
        <p className={`type-body-s ${styles.rationale}`}>{rec.rationale}</p>
      </div>
    </article>
  );
}
