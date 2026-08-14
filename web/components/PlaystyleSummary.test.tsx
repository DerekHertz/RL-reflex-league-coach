import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PlaystyleSummary } from "./PlaystyleSummary";
import type { PlaystyleVector } from "@/lib/api";
import { LOW_CONFIDENCE_CAVEAT } from "@/lib/presentation";

function makeVector(overrides: Partial<PlaystyleVector> = {}): PlaystyleVector {
  return {
    aggression: 0.6137254901960784,
    farming: 0.5529411764705883,
    vision: 0.4666666666666667,
    objective_focus: 0.47058823529411764,
    risk_tolerance: 0.5147058823529411,
    teamfight_vs_split: 0.5205882352941177,
    sample_size: 10,
    confidence: 0.7305186545882689,
    ...overrides,
  };
}

describe("PlaystyleSummary", () => {
  it("renders all six axes as bars with humanized labels and rounded percentages", () => {
    const { container } = render(<PlaystyleSummary playstyle={makeVector()} />);

    const fills = container.querySelectorAll('div[class*="fill"]');
    expect(fills).toHaveLength(6);

    expect(screen.getByText("aggression")).toBeInTheDocument();
    expect(screen.getByText("farming")).toBeInTheDocument();
    expect(screen.getByText("vision control")).toBeInTheDocument();
    expect(screen.getByText("objective focus")).toBeInTheDocument();
    expect(screen.getByText("risk tolerance")).toBeInTheDocument();
    expect(screen.getByText("teamfighting vs. split-pushing")).toBeInTheDocument();

    // Never raw snake_case.
    expect(screen.queryByText(/objective_focus/)).not.toBeInTheDocument();
    expect(screen.queryByText(/teamfight_vs_split/)).not.toBeInTheDocument();

    expect(screen.getByText("61%")).toBeInTheDocument(); // aggression
    expect(screen.getByText("55%")).toBeInTheDocument(); // farming
  });

  it("sets each bar's fill width from its 0..1 score", () => {
    const { container } = render(
      <PlaystyleSummary
        playstyle={makeVector({
          aggression: 0.5,
          farming: 0.5,
          vision: 0.5,
          objective_focus: 0.5,
          risk_tolerance: 0.5,
          teamfight_vs_split: 0.9,
        })}
      />,
    );
    const fills = container.querySelectorAll('div[class*="fill"]');
    expect((fills[0] as HTMLElement).style.width).toBe("50%");
    expect((fills[5] as HTMLElement).style.width).toBe("90%");
  });

  it("shows the sample-size caption", () => {
    render(<PlaystyleSummary playstyle={makeVector({ sample_size: 10 })} />);
    expect(screen.getByText(/based on 10 recent games/)).toBeInTheDocument();
  });

  it("omits the low-confidence caveat when confidence is at or above the threshold", () => {
    render(<PlaystyleSummary playstyle={makeVector({ confidence: 0.5 })} />);
    expect(screen.queryByText(new RegExp(LOW_CONFIDENCE_CAVEAT))).not.toBeInTheDocument();
  });

  it("shows the low-confidence caveat when confidence is below the threshold", () => {
    render(<PlaystyleSummary playstyle={makeVector({ confidence: 0.3 })} />);
    expect(screen.getByText(new RegExp(LOW_CONFIDENCE_CAVEAT.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))).toBeInTheDocument();
  });
});
