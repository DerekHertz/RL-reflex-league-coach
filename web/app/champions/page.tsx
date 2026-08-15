"use client";

import Link from "next/link";
import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { PlaystyleSummary } from "@/components/PlaystyleSummary";
import { ChampionRecCard } from "@/components/ChampionRecCard";
import { Disclaimer } from "@/components/Disclaimer";
import { AnalysisProgress } from "@/components/AnalysisProgress";
import { useSession } from "@/lib/session";
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
  const { riotId, analysis, champions, analyze } = useSession();
  const [inputValue, setInputValue] = useState(riotId);
  const [role, setRole] = useState<Role | "">("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // A role filter is a refinement of already-indexed data, not a reason to
  // re-run the full analyze() pipeline -- so it's its own direct fetch,
  // local to this page, layered on top of the shared "any role" result
  // rather than written back to SessionContext.
  const [roleStatus, setRoleStatus] = useState<Status>("idle");
  const [roleData, setRoleData] = useState<ChampionsResponse | null>(null);
  const [roleNotIndexed, setRoleNotIndexed] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);

  async function runRoleQuery(id: string, r: Role) {
    setRoleStatus("loading");
    setRoleData(null);
    setRoleNotIndexed(null);
    setRoleError(null);

    try {
      const result = await getChampionRecommendations(id, r);
      setRoleData(result);
      setRoleStatus("done");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setRoleNotIndexed(err.detail);
      } else {
        setRoleError(err instanceof Error ? err.message : String(err));
      }
      setRoleStatus("error");
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!inputValue.includes("#")) {
      setValidationError("Enter a Riot ID as gameName#tagLine, e.g. Player#NA1");
      return;
    }
    setValidationError(null);
    if (role === "") {
      analyze(inputValue);
    } else {
      void runRoleQuery(inputValue, role);
    }
  }

  function handleRetry() {
    if (role === "") {
      analyze(inputValue);
    } else {
      void runRoleQuery(inputValue, role);
    }
  }

  const usingRoleFilter = role !== "";
  const data = usingRoleFilter ? roleData : champions.data;
  const busy = usingRoleFilter ? roleStatus === "loading" : analysis.status === "loading" || champions.status === "loading";
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
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="gameName#tagLine, e.g. Player#NA1"
                disabled={busy}
                className={styles.input}
              />
            </label>
            <label className={styles.field}>
              <span className={`type-ui ${styles.label}`}>Role</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as Role | "")}
                disabled={busy}
                className={styles.select}
              >
                {ROLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" disabled={busy} busy={busy} busyLabel="Matching…">
              Find champions
            </Button>
          </form>

          {!usingRoleFilter && <AnalysisProgress />}
        </section>

        {validationError && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Lookup failed</p>
            <p className={styles.errorMessage}>{validationError}</p>
          </section>
        )}

        {usingRoleFilter && roleNotIndexed && (
          <section className={styles.notIndexedPanel}>
            <p className={`type-eyebrow ${styles.notIndexedEyebrow}`}>No history indexed yet</p>
            <p className={`type-body ${styles.notIndexedMessage}`}>{roleNotIndexed}</p>
            <Link href="/" className={`type-ui ${styles.indexLink}`}>
              Analyze a match to index this player
            </Link>
          </section>
        )}

        {!usingRoleFilter && champions.status === "loading" && analysis.status !== "loading" && (
          <p className={`type-ui ${styles.lede}`}>Loading your champion recommendations…</p>
        )}

        {((usingRoleFilter && roleStatus === "error" && roleError) || (!usingRoleFilter && champions.status === "error" && champions.error)) && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Lookup failed</p>
            <p className={styles.errorMessage}>{usingRoleFilter ? roleError : champions.error}</p>
            <Button variant="secondary" tone="ink" onClick={handleRetry}>
              Retry
            </Button>
          </section>
        )}

        {data && (
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
