"use client";

import { useEffect, useRef, useState } from "react";
import { ResultView } from "@/components/ResultView";
import { API_BASE, AnalysisEvent, AnalysisResult, startAnalysis } from "@/lib/api";

type Status = "idle" | "running" | "done" | "error";

export default function Home() {
  const [riotId, setRiotId] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!riotId.includes("#")) {
      setError("Enter a Riot ID as gameName#tagLine, e.g. Player#NA1");
      return;
    }

    setError(null);
    setResult(null);
    setStatus("running");
    setProgress(0);
    setMessage("Starting...");

    try {
      const { job_id } = await startAnalysis(riotId);
      const es = new EventSource(`${API_BASE}/api/analysis/${job_id}/events`);
      eventSourceRef.current = es;

      es.onmessage = (evt) => {
        const data: AnalysisEvent = JSON.parse(evt.data);
        setProgress(data.progress);
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

  return (
    <main
      style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: "2rem 1rem",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1>LoL Post-Game Coach</h1>
      <p style={{ color: "#666" }}>
        Enter your Riot ID to get a peer-relative breakdown of your most
        recent game, benchmarked against the other 9 players in that same
        match.
      </p>

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: 8, marginTop: 16 }}
      >
        <input
          value={riotId}
          onChange={(e) => setRiotId(e.target.value)}
          placeholder="gameName#tagLine, e.g. Player#NA1"
          disabled={status === "running"}
          style={{ flex: 1, padding: "8px 10px", fontSize: 16 }}
        />
        <button
          type="submit"
          disabled={status === "running"}
          style={{ padding: "8px 16px" }}
        >
          {status === "running" ? "Analyzing..." : "Analyze"}
        </button>
      </form>

      {status === "running" && (
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              background: "#eee",
              borderRadius: 4,
              overflow: "hidden",
              height: 8,
            }}
          >
            <div
              style={{
                width: `${Math.round(progress * 100)}%`,
                background: "#3b82f6",
                height: "100%",
                transition: "width 0.3s",
              }}
            />
          </div>
          <p style={{ color: "#666", fontSize: 14, marginTop: 6 }}>{message}</p>
        </div>
      )}

      {error && <p style={{ color: "#b91c1c", marginTop: 16 }}>{error}</p>}

      {status === "done" && result && <ResultView result={result} />}

      <footer
        style={{
          marginTop: 48,
          paddingTop: 16,
          borderTop: "1px solid #eee",
          color: "#999",
          fontSize: 12,
        }}
      >
        This tool isn&apos;t endorsed by Riot Games and doesn&apos;t reflect
        the views or opinions of Riot Games or anyone officially involved in
        producing or managing Riot Games properties.
      </footer>
    </main>
  );
}
