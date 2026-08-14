import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChampionRecCard } from "./ChampionRecCard";
import type { ChampionRec } from "@/lib/api";

const comfortRec: ChampionRec = {
  champion: "Kaisa",
  roles: ["BOTTOM"],
  fit_score: 0.9891,
  kind: "comfort",
  matched_axes: ["teamfight_vs_split", "aggression", "farming"],
  stretch_axis: null,
  rationale:
    "Evolving hybrid carry who dives into fights with invisibility and jump resets. Lines up with " +
    "how you already play: teamfighting vs. split-pushing, aggression, farming.",
};

const stretchRec: ChampionRec = {
  champion: "Shen",
  roles: ["TOP"],
  fit_score: 0.71,
  kind: "stretch",
  matched_axes: ["farming"],
  stretch_axis: "objective_focus",
  rationale:
    "Stoic protector who teleports across the map. A stretch pick: strong fit everywhere except " +
    "objective focus, where trying this champion means growing that side of your game.",
};

describe("ChampionRecCard", () => {
  it("renders a comfort card: champion, roles, fit score, and rationale, with no stretch tag", () => {
    render(<ChampionRecCard rec={comfortRec} />);
    expect(screen.getByText("Kaisa")).toBeInTheDocument();
    expect(screen.getByText("BOTTOM")).toBeInTheDocument();
    expect(screen.getByText("99% fit")).toBeInTheDocument();
    expect(screen.getByText(/Evolving hybrid carry/)).toBeInTheDocument();
    expect(screen.queryByText(/Stretch pick/)).not.toBeInTheDocument();
  });

  it("renders a stretch card with a distinct, humanized stretch-axis callout", () => {
    render(<ChampionRecCard rec={stretchRec} />);
    expect(screen.getByText("Shen")).toBeInTheDocument();
    expect(screen.getByText(/Stretch pick/)).toBeInTheDocument();
    expect(screen.getAllByText(/objective focus/).length).toBeGreaterThan(0);
  });

  it("never renders a raw snake_case axis name anywhere in the card", () => {
    const { container } = render(<ChampionRecCard rec={stretchRec} />);
    expect(container.textContent).not.toMatch(/objective_focus/);
    expect(container.textContent).not.toMatch(/teamfight_vs_split/);
  });
});
