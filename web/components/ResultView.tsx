import { AnalysisResult } from "@/lib/api";
import { ReportHeader } from "./ReportHeader";
import { WhatWentWell } from "./WhatWentWell";
import { FindingCard } from "./FindingCard";
import { ClosingLine } from "./ClosingLine";
import { ChatPanel } from "./ChatPanel";
import { Disclaimer } from "./Disclaimer";
import { RankStrip } from "./RankStrip";
import { SkillBandList } from "./SkillBandList";
import { CannotSeePanel } from "./CannotSeePanel";
import styles from "./ResultView.module.css";

export function ResultView({ result }: { result: AnalysisResult }) {
  const { fact_sheet: sheet, narrative } = result;
  const narrationByFindingId = new Map(narrative.narrations.map((n) => [n.finding_id, n]));

  return (
    <div className={styles.grid}>
      <main className={styles.main}>
        <ReportHeader
          sheet={sheet}
          headline={narrative.headline}
          model={result.model}
          elapsedS={result.elapsed_s}
          usedFallback={result.used_fallback}
        />

        <WhatWentWell items={narrative.what_went_well} />

        {sheet.findings.length > 0 && (
          <section className={styles.findings}>
            {sheet.findings.map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                narration={narrationByFindingId.get(finding.id) ?? null}
              />
            ))}
          </section>
        )}

        {sheet.clean_checks.length > 0 && (
          <section className={styles.cleanChecks}>
            <p className={`type-eyebrow ${styles.cleanEyebrow}`}>Checked, no issues</p>
            <ul className={styles.cleanList}>
              {sheet.clean_checks.map((check) => (
                <li key={check.id} className="type-body-s">
                  {check.title}
                </li>
              ))}
            </ul>
          </section>
        )}

        <ClosingLine text={narrative.closing} />

        <ChatPanel sheet={sheet} narrative={narrative} />

        <Disclaimer />
      </main>

      <aside className={styles.rail}>
        {sheet.metrics.length > 0 && (
          <section className={styles.railSection}>
            <p className={`type-eyebrow ${styles.railEyebrow}`}>Metrics</p>
            <div className={styles.metricsList}>
              {sheet.metrics.map((metric) => (
                <RankStrip key={metric.id} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {sheet.skill_scores.length > 0 && (
          <section className={styles.railSection}>
            <p className={`type-eyebrow ${styles.railEyebrow}`}>Skill read</p>
            <SkillBandList scores={sheet.skill_scores} />
          </section>
        )}

        <CannotSeePanel items={sheet.not_knowable} />
      </aside>
    </div>
  );
}
