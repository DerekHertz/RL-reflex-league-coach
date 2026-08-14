"use client";

import { useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/Button";
import { PulseDot } from "@/components/PulseDot";
import { ResultView } from "@/components/ResultView";
import { API_BASE, AnalysisEvent, AnalysisResult, startAnalysis } from "@/lib/api";
import { fetchProgressLabel } from "@/lib/presentation";
import styles from "./page.module.css";

type Status = "idle" | "running" | "done" | "error";

function statusLine(stage: string, message: string): string {
  if (stage === "fetching") return fetchProgressLabel(message);
  if (stage === "analyzing" || stage === "narrating") return `${stage} · ${message}`;
  return message;
}

export default function Home() {
  const [riotId, setRiotId] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  async function runAnalysis(id: string) {
    setError(null);
    setResult(null);
    setStatus("running");
    setProgress(0);
    setStage("queued");
    setMessage("Starting...");

    try {
      const { job_id } = await startAnalysis(id);
      const es = new EventSource(`${API_BASE}/api/analysis/${job_id}/events`);
      eventSourceRef.current = es;

      es.onmessage = (evt) => {
        const data: AnalysisEvent = JSON.parse(evt.data);
        setProgress(data.progress);
        setStage(data.stage);
        setMessage(data.message);

        if (data.status === "done") {
          setStatus("done");
          setResult(data.result);
          es.close();
        } else if (data.status === "error") {
          setStatus("error");
          setError(data.error ?? "Analysis failed for an unknown reason.");
          es.close();
        }
      };

      es.onerror = () => {
        setStatus("error");
        setError("Lost connection to the analysis stream.");
        es.close();
      };
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!riotId.includes("#")) {
      setError("Enter a Riot ID as gameName#tagLine, e.g. Player#NA1");
      setStatus("error");
      return;
    }
    void runAnalysis(riotId);
  }

  function handleRetry() {
    void runAnalysis(riotId);
  }

  const running = status === "running";

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
                value={riotId}
                onChange={(e) => setRiotId(e.target.value)}
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
                <div className={styles.progressFill} style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
              <p className={styles.statusLine}>
                <PulseDot />
                <span>{statusLine(stage, message)}</span>
              </p>
            </div>
          )}
        </section>

        {status === "error" && error && (
          <section className={styles.errorPanel}>
            <p className={`type-eyebrow ${styles.errorEyebrow}`}>Analysis failed</p>
            <p className={styles.errorMessage}>{error}</p>
            <Button variant="secondary" tone="ink" onClick={handleRetry}>
              Retry
            </Button>
          </section>
        )}

        {status === "done" && result && <ResultView result={result} />}
      </div>
    </>
  );
}
