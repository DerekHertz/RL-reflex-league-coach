import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SkillBandRow } from "./SkillBandRow";
import type { SkillScore } from "@/lib/api";

describe("SkillBandRow", () => {
  it("renders BELOW LOBBY in the bad color", () => {
    const score: SkillScore = { skill: "survivability", band: "below_lobby", basis: ["time_dead"] };
    render(<SkillBandRow score={score} />);
    const label = screen.getByText("BELOW LOBBY");
    expect(label).toBeInTheDocument();
    expect(label.style.color).toBe("var(--bad)");
  });

  it("renders AT LOBBY in neutral ink", () => {
    const score: SkillScore = { skill: "economy", band: "at_lobby", basis: ["unspent_gold"] };
    render(<SkillBandRow score={score} />);
    const label = screen.getByText("AT LOBBY");
    expect(label).toBeInTheDocument();
    expect(label.style.color).toBe("var(--ink-400)");
  });

  it("renders ABOVE LOBBY in the good color, even though v1 never emits it", () => {
    const score: SkillScore = { skill: "vision", band: "above_lobby", basis: ["ward_uptime"] };
    render(<SkillBandRow score={score} />);
    const label = screen.getByText("ABOVE LOBBY");
    expect(label).toBeInTheDocument();
    expect(label.style.color).toBe("var(--good)");
  });
});
