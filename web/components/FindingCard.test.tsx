import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FindingCard } from "./FindingCard";
import type { FindingFact, FindingNarration } from "@/lib/api";

function makeFinding(overrides: Partial<FindingFact> = {}): FindingFact {
  return {
    id: "time_dead:0",
    title: "Time spent dead",
    severity: "major",
    phase: "whole_game",
    confidence: 1,
    what_happened: "56.3% of the game was spent dead, across 9 deaths.",
    timestamps: ["22:21"],
    evidence: [
      { label: "Number of deaths", value: 9, unit: "count", peer_value: null, peer_label: null },
      { label: "Peak unspent gold", value: 3009, unit: "gold", peer_value: null, peer_label: null },
    ],
    ...overrides,
  };
}

const narration: FindingNarration = {
  finding_id: "time_dead:0",
  explanation: "explanation text",
  fix: "hold your escape",
  drill: "track deaths for 3 games",
};

describe("FindingCard", () => {
  it("renders the title, severity word, and formatted evidence", () => {
    render(<FindingCard finding={makeFinding()} narration={narration} />);

    expect(screen.getByText("Time spent dead")).toBeInTheDocument();
    expect(screen.getByText("MAJOR")).toBeInTheDocument();
    expect(screen.getByText("time_dead:0")).toBeInTheDocument();
    expect(screen.getByText(/Number of deaths/)).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("3,009")).toBeInTheDocument();
    expect(screen.getByText(/hold your escape/)).toBeInTheDocument();
    expect(screen.getByText(/track deaths for 3 games/)).toBeInTheDocument();
    expect(screen.getByText("Fix:")).toBeInTheDocument();
    expect(screen.getByText("Drill:")).toBeInTheDocument();
  });

  it("renders the single-timestamp evidence item verbatim", () => {
    render(<FindingCard finding={makeFinding()} narration={null} />);
    expect(screen.getByText(/Timestamps/)).toBeInTheDocument();
    expect(screen.getByText("22:21")).toBeInTheDocument();
  });

  it("renders a timestamp range for multiple timestamps", () => {
    render(
      <FindingCard
        finding={makeFinding({ timestamps: ["18:00", "24:00"] })}
        narration={null}
      />,
    );
    expect(screen.getByText("18:00 – 24:00")).toBeInTheDocument();
  });

  it("omits Fix/Drill paragraphs when there is no matching narration", () => {
    render(<FindingCard finding={makeFinding()} narration={null} />);
    expect(screen.queryByText("Fix:")).not.toBeInTheDocument();
    expect(screen.queryByText("Drill:")).not.toBeInTheDocument();
  });

  it("has no head tint for minor severity", () => {
    const { container } = render(
      <FindingCard finding={makeFinding({ severity: "minor" })} narration={null} />,
    );
    const head = container.querySelector("header");
    expect(head).not.toBeNull();
    expect(head?.style.getPropertyValue("--head-tint-pct")).toBe("0%");
  });

  it("has a nonzero head tint for major and moderate severity", () => {
    const majorRender = render(
      <FindingCard finding={makeFinding({ severity: "major" })} narration={null} />,
    );
    const majorHead = majorRender.container.querySelector("header");
    expect(majorHead?.style.getPropertyValue("--head-tint-pct")).toBe("7%");
    majorRender.unmount();

    const moderateRender = render(
      <FindingCard finding={makeFinding({ severity: "moderate" })} narration={null} />,
    );
    const moderateHead = moderateRender.container.querySelector("header");
    expect(moderateHead?.style.getPropertyValue("--head-tint-pct")).toBe("9%");
  });
});
