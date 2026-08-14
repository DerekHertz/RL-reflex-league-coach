"use client";

import Link from "next/link";
import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { ApiError, LedgerEntry, PoolChampionEntry, PoolResponse, getPool } from "@/lib/api";
import styles from "./page.module.css";

type Status = "idle" | "loading" | "done" | "error";

// Mirrors storage/repo.py's MIN_LEDGER_SAMPLE -- a champion with fewer
// cached games than this is shown locked rather than with noisy rates.
const MIN_SAMPLE = 3;

export default function PoolPage() {
  const [riotId, setRiotId] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [data, setData] = useState<PoolResponse | null>(null);
  const [notIndexed, setNotIndexed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runLookup(id: string) {
    setStatus("loading");
    setData(null);
    setNotIndexed(null);
    setError(null);

    try {
      const result = await getPool(id);
      setData(result);
      setStatus("done");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotIndexed(err.detail);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
      setStatus("error");
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!riotId.includes("#")) {
      setError("Enter a Riot ID as gameName#tagLine, e.g. Player#NA1");
      setNotIndexed(null);
      setStatus("error");
      return;
    }
    void runLookup(riotId);
  }

  function handleRetry() {
    void runLookup(riotId);
  }

  const loading = status === "loading";

  return (
    <>
      <TopBar />
      <div className={styles.page}>
        <section className={styles.intake}>
          <h1 className="type-display-l">Your pool</h1>
          <p className={`type-body ${styles.lede}`}>
            Enter your Riot ID to see how often each check has fired, broken down by champion. Play
            three games on a champion to unlock its stats.
          </p>

          <form onSubmit={handleSubmit} className={styles.form}>
            <label className={`${styles.field} ${styles.riotIdField}`}>
              <span className={`type-ui ${styles.label}`}>Riot ID</span>
              <input
                value={riotId}
                onChange={(e) => setRiotId(e.target.value)}
                placeholder="gameName#tagLine, e.g. Player#NA1"
                disabled={loading}
                className={styles.input}
              />
            </label>
            <Button type="submit" disabled={loading} busy={loading} busyLabel="Reading…">
              Show my pool
            </Button>
          </form>
        </section>

        {status === "error" && notIndexed && (
          <section className={styles.notIndexedPanel}>
            <p className={`type-eyebrow ${styles.notIndexedEyebrow}`}>No history indexed yet</p>
            <p className={`type-body ${styles.notIndexedMessage}`}>{notIndexed}</p>
            <Link href="/" className={`type-ui ${styles.indexLink}`}>
              Analyze a match to index this player
            </Link>
          </section>
        )}

        {status === "error" && error && !notIndexed && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Lookup failed</p>
            <p className={styles.errorMessage}>{error}</p>
            <Button variant="secondary" tone="ink" onClick={handleRetry}>
              Retry
            </Button>
          </section>
        )}

        {status === "done" && data && (
          <div className={styles.report}>
            {data.champions.length === 0 ? (
              <p className={`type-body ${styles.lede}`}>
                No analyzed matches yet for this player -- run an analysis first.
              </p>
            ) : (
              data.champions.map((champion) => <ChampionSection key={champion.champion_id} champion={champion} />)
            )}
            <Disclaimer />
          </div>
        )}
      </div>
    </>
  );
}

function ChampionSection({ champion }: { champion: PoolChampionEntry }) {
  const locked = champion.games_played < MIN_SAMPLE;
  return (
    <section className={`${styles.champion} ${locked ? styles.locked : ""}`}>
      <div className={styles.champHeader}>
        <span className={`type-eyebrow ${styles.champName}`}>{champion.champion_name}</span>
        <span className={`type-ui ${styles.champGames}`}>
          {champion.games_played} game{champion.games_played === 1 ? "" : "s"}
        </span>
      </div>
      {locked ? (
        <p className={`type-ui ${styles.lockedMessage}`}>
          {MIN_SAMPLE - champion.games_played} more game{MIN_SAMPLE - champion.games_played === 1 ? "" : "s"} to
          unlock this champion&apos;s stats
        </p>
      ) : (
        <ul className={styles.entries}>
          {champion.entries.map((entry) => (
            <PoolRow key={entry.detector_key} entry={entry} />
          ))}
        </ul>
      )}
    </section>
  );
}

function PoolRow({ entry }: { entry: LedgerEntry }) {
  const belowMinSample = entry.rate === null;
  return (
    <li className={`${styles.entry} ${belowMinSample ? styles.entryLocked : ""}`}>
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
