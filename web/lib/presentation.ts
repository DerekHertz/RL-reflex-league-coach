// Pure, render-free helpers that translate API data into presentation
// decisions (colors, labels, formatted strings). Kept separate from
// components so they're unit-testable without React Testing Library.

export type Severity = "info" | "minor" | "moderate" | "major";
export type Band = "below_lobby" | "at_lobby" | "above_lobby";
export type Tercile = "good" | "mid" | "bad";
export type Peer = "lane_opponent" | "role_cohort_avg";

/** CSS var reference for a severity's semantic color. Unknown/"info"
 * severities fall back to the minor treatment -- never crash on unexpected
 * data, never invent a fourth visual tier the spec doesn't define. */
export function severityColorVar(severity: string): string {
  if (severity === "major") return "var(--sev-major)";
  if (severity === "moderate") return "var(--sev-moderate)";
  return "var(--sev-minor)";
}

/** The word is always present -- never color-only. */
export function severityLabel(severity: string): "MAJOR" | "MODERATE" | "MINOR" {
  if (severity === "major") return "MAJOR";
  if (severity === "moderate") return "MODERATE";
  return "MINOR";
}

/** FindingCard head tint opacity for a severity tag. 0 means "no tint" (minor). */
export function findingHeadTintOpacity(severity: string): number {
  if (severity === "major") return 0.07;
  if (severity === "moderate") return 0.09;
  return 0;
}

/** DetectorChip tint opacities, matching the FindingCard tint logic:
 * background at 10%, border at 30%, text left at full (mono) strength. */
export const DETECTOR_CHIP_BG_OPACITY = 0.1;
export const DETECTOR_CHIP_BORDER_OPACITY = 0.3;

export function bandLabel(band: string): string {
  switch (band) {
    case "below_lobby":
      return "BELOW LOBBY";
    case "at_lobby":
      return "AT LOBBY";
    case "above_lobby":
      return "ABOVE LOBBY";
    default:
      return band.toUpperCase();
  }
}

export function bandColorVar(band: string): string {
  switch (band) {
    case "below_lobby":
      return "var(--bad)";
    case "above_lobby":
      return "var(--good)";
    default:
      // at_lobby, and any unrecognized band: neutral ink, not a severity color.
      return "var(--ink-400)";
  }
}

/** Splits a 1-based rank out of `total` peers into thirds. For the spec's
 * 10-cell strip this yields exactly rank<=3 good, rank<=7 mid, rank>7 bad. */
export function rankTercile(rank: number, total = 10): Tercile {
  const lowerBound = Math.round(total / 3);
  const upperBound = Math.round((2 * total) / 3);
  if (rank <= lowerBound) return "good";
  if (rank <= upperBound) return "mid";
  return "bad";
}

export function rankTercileColorVar(tercile: Tercile): string {
  switch (tercile) {
    case "good":
      return "var(--jade-600)";
    case "mid":
      return "var(--gold-500)";
    case "bad":
      return "var(--red-600)";
  }
}

export function peerLabel(peer: Peer): string {
  return peer === "lane_opponent" ? "lane opponent" : "role cohort";
}

export function resultLabel(result: "win" | "loss"): "VICTORY" | "DEFEAT" {
  return result === "win" ? "VICTORY" : "DEFEAT";
}

/** Integers render bare, non-integers get exactly one decimal place. */
export function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Evidence-strip value formatting: percent gets a %, gold gets thousands
 * separators, count stays a plain number, anything else gets the raw unit
 * name appended so a bare number is never shown with no context. */
export function formatEvidenceValue(value: number, unit: string): string {
  if (unit === "percent") return `${formatNumber(value)}%`;
  if (unit === "gold") return Math.round(value).toLocaleString("en-US");
  if (unit === "count") return formatNumber(value);
  return `${formatNumber(value)} ${unit}`;
}

/** Turns a backend progress message like "Fetching match 3/5: NA1_..." into
 * a terse mono status line ("pulling 3/5 matches"). Falls back to the raw
 * message verbatim if it doesn't match the expected shape, so an unexpected
 * backend message still renders instead of disappearing. */
export function fetchProgressLabel(message: string): string {
  const match = message.match(/fetching match (\d+)\s*\/\s*(\d+)/i);
  if (!match) return message;
  return `pulling ${match[1]}/${match[2]} matches`;
}

/** Renders a finding's timestamps as a single evidence-strip value: null if
 * empty, the bare value if there's one, else a range from first to last. */
export function formatTimestamps(timestamps: string[]): string | null {
  if (timestamps.length === 0) return null;
  if (timestamps.length === 1) return timestamps[0];
  return `${timestamps[0]} – ${timestamps[timestamps.length - 1]}`;
}
