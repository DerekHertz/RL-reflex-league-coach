"use client";

import Link from "next/link";
import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { PlaystyleSummary } from "@/components/PlaystyleSummary";
import { ChampionRecCard } from "@/components/ChampionRecCard";
import { Disclaimer } from "@/components/Disclaimer";
import { ApiError, ChampionsResponse, getChampionRecommendations, Role } from "@/lib/api";
import { recKindEyebrow } from "@/lib/presentation";
import styles from "./page.module.css";

type Status = "idle" | "loading" | "done" | "error";

const ROLE_OPTIONS: { value: Role | ""; label: string }[] = [
  { value: "", label: "Any role" },
  { value: "TOP", label: "Top" },
  { value: "JUNGLE", label: "Jungle" },
  { value: "MIDDLE", label: "Mid" },
  { value: "BOTTOM", label: "Bottom" },
  { value: "UTILITY", label: "Support" },
];

export default function ChampionsPage() {
  const [riotId, setRiotId] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [status, setStatus] = useState<Status>("idle");
  const [data, setData] = useState<ChampionsResponse | null>(null);
  const [notIndexed, setNotIndexed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runLookup(id: string, r: Role | "") {
    setStatus("loading");
    setData(null);
    setNotIndexed(null);
    setError(null);

    try {
      const result = await getChampionRecommendations(id, r === "" ? null : r);
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
    void runLookup(riotId, role);
  }

  function handleRetry() {
    void runLookup(riotId, role);
  }

  const loading = status === "loading";
  const comfortRecs = data?.recommendations.filter((r) => r.kind === "comfort") ?? [];
  const stretchRecs = data?.recommendations.filter((r) => r.kind === "stretch") ?? [];

  return (
    <>
      <TopBar />
      <div className={styles.page}>
        <section className={styles.intake}>
          <h1 className="type-display-l">Champion fit</h1>
          <p className={`type-body ${styles.lede}`}>
            Enter your Riot ID to see how your recent games map onto six playstyle traits, and which
            champions line up with that read.
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
            <label className={styles.field}>
              <span className={`type-ui ${styles.label}`}>Role</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as Role | "")}
                disabled={loading}
                className={styles.select}
              >
                {ROLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" disabled={loading} busy={loading} busyLabel="Matching…">
              Find champions
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
            <PlaystyleSummary playstyle={data.playstyle} />

            {comfortRecs.length > 0 && (
              <section className={styles.recSection}>
                <p className={`type-eyebrow ${styles.recEyebrow}`}>{recKindEyebrow("comfort")}</p>
                <div className={styles.recCards}>
                  {comfortRecs.map((rec) => (
                    <ChampionRecCard key={rec.champion} rec={rec} />
                  ))}
                </div>
              </section>
            )}

            {stretchRecs.length > 0 && (
              <section className={styles.recSection}>
                <p className={`type-eyebrow ${styles.recEyebrow}`}>{recKindEyebrow("stretch")}</p>
                <div className={styles.recCards}>
                  {stretchRecs.map((rec) => (
                    <ChampionRecCard key={rec.champion} rec={rec} />
                  ))}
                </div>
              </section>
            )}

            <Disclaimer />
          </div>
        )}
      </div>
    </>
  );
}
