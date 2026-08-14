import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportHeader } from "./ReportHeader";
import type { MatchFactSheet } from "@/lib/api";

const sheet: MatchFactSheet = {
  subject: { champion: "Aurora", role: "MIDDLE" },
  match: { queue_name: "Normal Draft", patch: "16.16", duration: "29:31", result: "win", team_side: "blue" },
  lane_opponent: { champion: "Zoe", role: "MIDDLE" },
  metrics: [],
  findings: [],
  clean_checks: [],
  skipped_checks: [],
  skill_scores: [],
  not_knowable: [],
};

describe("ReportHeader", () => {
  it("attributes the narration to Claude when the structured response validated", () => {
    render(<ReportHeader sheet={sheet} headline="Headline" model="claude-opus-5" elapsedS={34.2} usedFallback={false} />);
    expect(screen.getByText("Narrated by Claude · claude-opus-5 · 34.2s")).toBeInTheDocument();
  });

  it("does not claim Claude narrated it when the guard rejected the response and a fallback was used", () => {
    render(<ReportHeader sheet={sheet} headline="Headline" model="claude-opus-5" elapsedS={34.2} usedFallback={true} />);
    expect(screen.queryByText(/Narrated by Claude/)).not.toBeInTheDocument();
    expect(screen.getByText("claude-opus-5 attempted, didn't validate · 34.2s")).toBeInTheDocument();
  });
});
