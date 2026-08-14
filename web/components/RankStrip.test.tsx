import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RankStrip } from "./RankStrip";
import type { MetricFact } from "@/lib/api";

function makeMetric(overrides: Partial<MetricFact> = {}): MetricFact {
  return {
    id: "gold_per_minute",
    label: "Gold per minute",
    value: 839,
    unit: "per_minute",
    direction: "higher_better",
    comparisons: [
      { peer: "role_cohort_avg", peer_value: 610, delta: 229, rank_in_lobby: 2 },
    ],
    ...overrides,
  };
}

describe("RankStrip", () => {
  it("fills the cell at rank_in_lobby and colors it jade for a top-third rank", () => {
    const { container } = render(<RankStrip metric={makeMetric()} />);
    const cells = container.querySelectorAll('span[class*="cell"]');
    expect(cells).toHaveLength(10);
    // rank 2 -> index 1 (1-based position 2)
    expect(cells[1]).toHaveAttribute("data-filled", "true");
    expect((cells[1] as HTMLElement).style.background).toBe("var(--jade-600)");
    // every other cell is unfilled and neutral
    cells.forEach((cell, i) => {
      if (i === 1) return;
      expect(cell).not.toHaveAttribute("data-filled");
      expect((cell as HTMLElement).style.background).toBe("var(--paper-500)");
    });
    expect(screen.getByText(/rank 2\/10/)).toBeInTheDocument();
    expect(screen.getByText(/role cohort/)).toBeInTheDocument();
  });

  it("colors a middle-third rank gold", () => {
    const { container } = render(
      <RankStrip
        metric={makeMetric({
          comparisons: [{ peer: "lane_opponent", peer_value: 500, delta: 10, rank_in_lobby: 5 }],
        })}
      />,
    );
    const cells = container.querySelectorAll('span[class*="cell"]');
    expect((cells[4] as HTMLElement).style.background).toBe("var(--gold-500)");
    expect(screen.getByText(/lane opponent/)).toBeInTheDocument();
  });

  it("colors a bottom-third rank red", () => {
    const { container } = render(
      <RankStrip
        metric={makeMetric({
          comparisons: [{ peer: "role_cohort_avg", peer_value: 500, delta: -10, rank_in_lobby: 9 }],
        })}
      />,
    );
    const cells = container.querySelectorAll('span[class*="cell"]');
    expect((cells[8] as HTMLElement).style.background).toBe("var(--red-600)");
  });

  it("falls back to 'no peer comparison available' with all cells neutral when comparisons is empty", () => {
    const { container } = render(<RankStrip metric={makeMetric({ comparisons: [] })} />);
    const cells = container.querySelectorAll('span[class*="cell"]');
    cells.forEach((cell) => {
      expect(cell).not.toHaveAttribute("data-filled");
      expect((cell as HTMLElement).style.background).toBe("var(--paper-500)");
    });
    expect(screen.getByText("no peer comparison available")).toBeInTheDocument();
  });
});
