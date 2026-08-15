"use client";

import { ReactNode, createContext, useCallback, useContext, useRef, useState } from "react";
import {
  API_BASE,
  AnalysisEvent,
  AnalysisResult,
  ApiError,
  ChampionsResponse,
  LedgerResponse,
  PoolResponse,
  getChampionRecommendations,
  getLedger,
  getPool,
  startAnalysis,
} from "./api";

type Status = "idle" | "loading" | "done" | "error";

interface AnalysisState {
  status: Status;
  progress: number;
  stage: string;
  message: string;
  result: AnalysisResult | null;
  error: string | null;
}

interface ResourceState<T> {
  status: Status;
  data: T | null;
  error: string | null;
}

interface SessionValue {
  riotId: string;
  analysis: AnalysisState;
  champions: ResourceState<ChampionsResponse>;
  ledger: ResourceState<LedgerResponse>;
  pool: ResourceState<PoolResponse>;
  /** Runs the full pipeline for a Riot ID: /api/analysis (SSE), then --
   * once that job reports done -- champions/ledger/pool in parallel. Every
   * page reads its resource from here instead of managing its own fetch,
   * so navigating away and back doesn't require re-entering the ID or
   * waiting again. */
  analyze: (riotId: string) => void;
}

const idleAnalysis: AnalysisState = { status: "idle", progress: 0, stage: "", message: "", result: null, error: null };

function idleResource<T>(): ResourceState<T> {
  return { status: "idle", data: null, error: null };
}

function describeError(err: unknown): string {
  return err instanceof ApiError ? err.detail : err instanceof Error ? err.message : String(err);
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [riotId, setRiotId] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisState>(idleAnalysis);
  const [champions, setChampions] = useState<ResourceState<ChampionsResponse>>(idleResource);
  const [ledger, setLedger] = useState<ResourceState<LedgerResponse>>(idleResource);
  const [pool, setPool] = useState<ResourceState<PoolResponse>>(idleResource);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Fired only after /api/analysis reports "done" -- champions/ledger/pool
  // all read DB rows that analysis populates as a side effect (the player
  // row, indexed matches, finding_outcome rows), so firing them any
  // earlier risks a 404 (player not yet upserted) or partial data.
  const fanOut = useCallback((id: string) => {
    setChampions({ status: "loading", data: null, error: null });
    setLedger({ status: "loading", data: null, error: null });
    setPool({ status: "loading", data: null, error: null });

    getChampionRecommendations(id).then(
      (data) => setChampions({ status: "done", data, error: null }),
      (err) => setChampions({ status: "error", data: null, error: describeError(err) }),
    );
    getLedger(id).then(
      (data) => setLedger({ status: "done", data, error: null }),
      (err) => setLedger({ status: "error", data: null, error: describeError(err) }),
    );
    getPool(id).then(
      (data) => setPool({ status: "done", data, error: null }),
      (err) => setPool({ status: "error", data: null, error: describeError(err) }),
    );
  }, []);

  const analyze = useCallback(
    (id: string) => {
      eventSourceRef.current?.close();
      setRiotId(id);
      setAnalysis({ status: "loading", progress: 0, stage: "queued", message: "Starting...", result: null, error: null });
      setChampions(idleResource());
      setLedger(idleResource());
      setPool(idleResource());

      startAnalysis(id)
        .then(({ job_id }) => {
          const es = new EventSource(`${API_BASE}/api/analysis/${job_id}/events`);
          eventSourceRef.current = es;

          es.onmessage = (evt) => {
            const data: AnalysisEvent = JSON.parse(evt.data);
            setAnalysis((prev) => ({ ...prev, progress: data.progress, stage: data.stage, message: data.message }));

            if (data.status === "done") {
              setAnalysis((prev) => ({ ...prev, status: "done", result: data.result }));
              es.close();
              fanOut(id);
            } else if (data.status === "error") {
              setAnalysis((prev) => ({ ...prev, status: "error", error: data.error ?? "Analysis failed for an unknown reason." }));
              es.close();
            }
          };

          es.onerror = () => {
            setAnalysis((prev) => ({ ...prev, status: "error", error: "Lost connection to the analysis stream." }));
            es.close();
          };
        })
        .catch((err) => {
          setAnalysis((prev) => ({ ...prev, status: "error", error: err instanceof Error ? err.message : String(err) }));
        });
    },
    [fanOut],
  );

  return (
    <SessionContext.Provider value={{ riotId, analysis, champions, ledger, pool, analyze }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
