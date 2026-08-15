"use client";

import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { AnalysisProgress } from "@/components/AnalysisProgress";
import { useSession } from "@/lib/session";
import { LedgerEntry } from "@/lib/api";
import styles from "./page.module.css";

export default function LedgerPage() {
  const { riotId, analysis, ledger, analyze } = useSession();
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

  const busy = analysis.status === "loading" || ledger.status === "loading";

  return (
    <>
      <TopBar />
      <div className={styles.page}>
        <section className={styles.intake}>
          <h1 className="type-display-l">Ledger</h1>
          <p className={`type-body ${styles.lede}`}>
            Enter your Riot ID to see how often each check has fired across every match you&apos;ve
            analyzed.
          </p>

          <form onSubmit={handleSubmit} className={styles.form}>
            <label className={`${styles.field} ${styles.riotIdField}`}>
              <span className={`type-ui ${styles.label}`}>Riot ID</span>
              <input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="gameName#tagLine, e.g. Player#NA1"
                disabled={busy}
                className={styles.input}
              />
            </label>
            <Button type="submit" disabled={busy} busy={busy} busyLabel="Reading…">
              Show ledger
            </Button>
          </form>

          <AnalysisProgress />
        </section>

        {validationError && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Lookup failed</p>
            <p className={styles.errorMessage}>{validationError}</p>
          </section>
        )}

        {ledger.status === "loading" && analysis.status !== "loading" && (
          <p className={`type-ui ${styles.lede}`}>Loading your ledger…</p>
        )}

        {ledger.status === "error" && ledger.error && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Lookup failed</p>
            <p className={styles.errorMessage}>{ledger.error}</p>
            <Button variant="secondary" tone="ink" onClick={handleRetry}>
              Retry
            </Button>
          </section>
        )}

        {ledger.status === "done" && ledger.data && (
          <div className={styles.report}>
            {ledger.data.entries.length === 0 ? (
              <p className={`type-body ${styles.lede}`}>
                No analyzed matches yet for this player -- run an analysis first.
              </p>
            ) : (
              <ul className={styles.entries}>
                {ledger.data.entries.map((entry) => (
                  <LedgerRow key={entry.detector_key} entry={entry} />
                ))}
              </ul>
            )}
            <Disclaimer />
          </div>
        )}
      </div>
    </>
  );
}

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  const belowMinSample = entry.rate === null;
  return (
    <li className={styles.entry}>
      <span className={`type-body ${styles.entryTitle}`}>{entry.title}</span>
      {belowMinSample ? (
        <span className={`type-ui ${styles.entryMuted}`}>
          {entry.total} game{entry.total === 1 ? "" : "s"} captured -- not enough data yet
        </span>
      ) : (
        <span className={`type-ui ${styles.entryStat}`}>
          Fired in {entry.fired}/{entry.total} games ({Math.round((entry.rate as number) * 100)}%)
        </span>
      )}
    </li>
  );
}
