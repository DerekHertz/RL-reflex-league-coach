"use client";

import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { PulseDot } from "@/components/PulseDot";
import { ResultView } from "@/components/ResultView";
import { useSession } from "@/lib/session";
import { fetchProgressLabel } from "@/lib/presentation";
import styles from "./page.module.css";

function statusLine(stage: string, message: string): string {
  if (stage === "fetching") return fetchProgressLabel(message);
  if (stage === "analyzing" || stage === "narrating") return `${stage} · ${message}`;
  return message;
}

export default function Home() {
  const { riotId, analysis, analyze } = useSession();
  const [inputValue, setInputValue] = useState(riotId);
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!inputValue.includes("#")) {
      setValidationError("Enter a Riot ID as gameName#tagLine, e.g. Player#NA1");
      return;
    }
    setValidationError(null);
    analyze(inputValue);
  }

  function handleRetry() {
    analyze(inputValue);
  }

  const running = analysis.status === "loading";

  return (
    <>
      <TopBar />
      <div className={styles.page}>
        <section className={styles.intake}>
          <h1 className="type-display-l">Last match</h1>
          <p className={`type-body ${styles.lede}`}>
            Enter your Riot ID for a peer-relative breakdown of your most recent game, benchmarked
            against the other nine players in that same match.
          </p>

          <form onSubmit={handleSubmit} className={styles.form}>
            <label className={styles.field}>
              <span className={`type-ui ${styles.label}`}>Riot ID</span>
              <input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="gameName#tagLine, e.g. Player#NA1"
                disabled={running}
                className={styles.input}
              />
            </label>
            <Button type="submit" disabled={running} busy={running} busyLabel="Reading…">
              Analyze
            </Button>
          </form>

          {running && (
            <div className={styles.progress}>
              <div className={styles.progressTrack}>
                <div className={styles.progressFill} style={{ width: `${Math.round(analysis.progress * 100)}%` }} />
              </div>
              <p className={styles.statusLine}>
                <PulseDot />
                <span>{statusLine(analysis.stage, analysis.message)}</span>
              </p>
            </div>
          )}
        </section>

        {validationError && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Analysis failed</p>
            <p className={styles.errorMessage}>{validationError}</p>
          </section>
        )}

        {!validationError && analysis.status === "error" && analysis.error && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Analysis failed</p>
            <p className={styles.errorMessage}>{analysis.error}</p>
            <Button variant="secondary" tone="ink" onClick={handleRetry}>
              Retry
            </Button>
          </section>
        )}

        {analysis.status === "done" && analysis.result && <ResultView result={analysis.result} />}
      </div>
    </>
  );
}
