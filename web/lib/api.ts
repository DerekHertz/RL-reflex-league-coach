// Minimal hand-written types mirroring the FastAPI DTOs in
// src/lolcoach/api/schemas.py, analysis/factsheet.py, and llm/schemas.py.
// Not generated from OpenAPI (that's a nicer setup for later) -- kept small
// and in sync by hand since the API surface is still tiny.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8420";

export interface MetaResponse {
  disclaimer: string;
  engine_version: string;
}

export interface EvidenceFact {
  label: string;
  value: number;
  unit: string;
  peer_value: number | null;
  peer_label: string | null;
}

export interface MetricComparison {
  peer: "lane_opponent" | "role_cohort_avg";
  peer_value: number;
  delta: number;
  rank_in_lobby: number | null;
}

export interface MetricFact {
  id: string;
  label: string;
  value: number;
  unit: string;
  direction: "higher_better" | "lower_better" | "neutral";
  comparisons: MetricComparison[];
}

export interface FindingFact {
  id: string;
  title: string;
  severity: "info" | "minor" | "moderate" | "major";
  phase: string;
  confidence: number;
  what_happened: string;
  timestamps: string[];
  evidence: EvidenceFact[];
}

export interface CleanCheck {
  id: string;
  title: string;
  evidence: EvidenceFact[];
}

export interface SkippedCheck {
  check: string;
  reason: string;
}

export interface SkillScore {
  skill: string;
  band: "below_lobby" | "at_lobby" | "above_lobby";
  basis: string[];
}

export interface MatchFactSheet {
  subject: { champion: string; role: string };
  match: {
    queue_name: string;
    patch: string;
    duration: string;
    result: "win" | "loss";
    team_side: "blue" | "red";
  };
  lane_opponent: { champion: string; role: string } | null;
  metrics: MetricFact[];
  findings: FindingFact[];
  clean_checks: CleanCheck[];
  skipped_checks: SkippedCheck[];
  skill_scores: SkillScore[];
  not_knowable: string[];
}

export interface FindingNarration {
  finding_id: string;
  explanation: string;
  fix: string;
  drill: string | null;
}

export interface CoachingResponse {
  headline: string;
  what_went_well: string[];
  focus_areas: string[];
  narrations: FindingNarration[];
  closing: string;
}

export interface AnalysisResult {
  puuid: string;
  match_id: string;
  other_match_ids: string[];
  fact_sheet: MatchFactSheet;
  narrative: CoachingResponse;
  used_fallback: boolean;
  /** Always "claude-opus-5" today, but treat as opaque -- narrated by whichever
   * model actually produced this narrative. */
  model: string;
  /** Wall-clock seconds the analysis job took, rounded to 1 decimal. */
  elapsed_s: number;
}

export interface AnalysisEvent {
  stage: string;
  progress: number;
  message: string;
  status: "queued" | "running" | "done" | "error";
  result: AnalysisResult | null;
  error: string | null;
}

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await fetch(`${API_BASE}/api/meta`);
  if (!res.ok) throw new Error(`GET /api/meta failed: ${res.status}`);
  return res.json();
}

export async function startAnalysis(
  riotId: string,
  count = 10,
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ riot_id: riotId, count }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`POST /api/analysis failed: ${res.status} ${body}`);
  }
  return res.json();
}

export type Role = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";

export interface PlaystyleVector {
  aggression: number;
  farming: number;
  vision: number;
  objective_focus: number;
  risk_tolerance: number;
  teamfight_vs_split: number;
  sample_size: number;
  confidence: number;
}

export interface ChampionRec {
  champion: string;
  roles: string[];
  fit_score: number;
  kind: "comfort" | "stretch";
  matched_axes: string[];
  stretch_axis: string | null;
  rationale: string;
}

export interface ChampionsResponse {
  playstyle: PlaystyleVector;
  recommendations: ChampionRec[];
  sample_size: number;
}

export interface LedgerEntry {
  detector_key: string;
  title: string;
  fired: number;
  total: number;
  /** null below the backend's minimum-sample threshold (3 matches) -- a
   * rate computed from 1-2 matches is noise, not signal. */
  rate: number | null;
}

export interface LedgerResponse {
  entries: LedgerEntry[];
}

export interface PoolChampionEntry {
  champion_id: number;
  champion_name: string;
  games_played: number;
  entries: LedgerEntry[];
}

export interface PoolResponse {
  champions: PoolChampionEntry[];
}

/** Carries the HTTP status alongside the backend's `detail` message so
 * callers can branch on status (e.g. 404 "never analyzed" vs any other
 * failure) without re-parsing the response body themselves. */
export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function getChampionRecommendations(
  riotId: string,
  role: Role | null = null,
): Promise<ChampionsResponse> {
  const res = await fetch(`${API_BASE}/api/champions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ riot_id: riotId, role }),
  });
  if (!res.ok) {
    let detail = `POST /api/champions failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body wasn't JSON (or empty) -- fall back to the generic message.
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function getLedger(riotId: string): Promise<LedgerResponse> {
  const res = await fetch(`${API_BASE}/api/ledger`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ riot_id: riotId }),
  });
  if (!res.ok) {
    let detail = `POST /api/ledger failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body wasn't JSON (or empty) -- fall back to the generic message.
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function getPool(riotId: string): Promise<PoolResponse> {
  const res = await fetch(`${API_BASE}/api/pool`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ riot_id: riotId }),
  });
  if (!res.ok) {
    let detail = `POST /api/pool failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body wasn't JSON (or empty) -- fall back to the generic message.
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}
