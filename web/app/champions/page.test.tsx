import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChampionsPage from "./page";

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

const NOT_INDEXED_DETAIL =
  "No indexed match history for this player yet. " +
  "Run POST /api/analysis first to fetch and index their recent matches, then retry.";

const CHAMPIONS_RESPONSE = {
  playstyle: {
    aggression: 0.6137254901960784,
    farming: 0.5529411764705883,
    vision: 0.4666666666666667,
    objective_focus: 0.47058823529411764,
    risk_tolerance: 0.5147058823529411,
    teamfight_vs_split: 0.5205882352941177,
    sample_size: 10,
    confidence: 0.7305186545882689,
  },
  recommendations: [
    {
      champion: "Kaisa",
      roles: ["BOTTOM"],
      fit_score: 0.9891,
      kind: "comfort",
      matched_axes: ["teamfight_vs_split", "aggression", "farming"],
      stretch_axis: null,
      rationale:
        "Evolving hybrid carry who dives into fights with invisibility and jump resets. Lines up with " +
        "how you already play: teamfighting vs. split-pushing, aggression, farming.",
    },
    {
      champion: "Xayah",
      roles: ["BOTTOM"],
      fit_score: 0.94,
      kind: "comfort",
      matched_axes: ["farming"],
      stretch_axis: null,
      rationale: "Feathered marksman with root setups. Lines up with how you already play: farming.",
    },
    {
      champion: "Draven",
      roles: ["BOTTOM"],
      fit_score: 0.9,
      kind: "comfort",
      matched_axes: ["aggression"],
      stretch_axis: null,
      rationale: "Showboating executioner. Lines up with how you already play: aggression.",
    },
    {
      champion: "Shen",
      roles: ["TOP"],
      fit_score: 0.71,
      kind: "stretch",
      matched_axes: ["farming"],
      stretch_axis: "objective_focus",
      rationale:
        "Stoic protector who teleports across the map. A stretch pick: strong fit everywhere except " +
        "objective focus, where trying this champion means growing that side of your game.",
    },
    {
      champion: "Janna",
      roles: ["UTILITY"],
      fit_score: 0.68,
      kind: "stretch",
      matched_axes: [],
      stretch_axis: "vision",
      rationale:
        "Wind-riding protector. A stretch pick: strong fit everywhere except vision control, where " +
        "trying this champion means growing that side of your game.",
    },
  ],
  sample_size: 10,
};

function stubFetch(championsHandler: () => Promise<Response> | Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/meta")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }),
        } as Response);
      }
      if (url.includes("/api/champions")) {
        return Promise.resolve(championsHandler());
      }
      throw new Error(`unexpected fetch to ${url}`);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function submitRiotId(id: string) {
  const user = userEvent.setup();
  await user.type(screen.getByPlaceholderText(/gameName#tagLine/), id);
  await user.click(screen.getByRole("button", { name: /find champions/i }));
}

describe("ChampionsPage", () => {
  beforeEach(() => {
    stubFetch(() => ({ ok: true, json: async () => CHAMPIONS_RESPONSE }) as Response);
  });

  it("shows only the form before any submission", () => {
    render(<ChampionsPage />);
    expect(screen.getByText("Champion fit")).toBeInTheDocument();
    expect(screen.queryByText("aggression")).not.toBeInTheDocument();
  });

  it("renders the playstyle summary and both recommendation groups on success", async () => {
    render(<ChampionsPage />);
    await submitRiotId("4DH#NA1");

    await waitFor(() => expect(screen.getByText("aggression")).toBeInTheDocument());

    // Playstyle bars.
    expect(screen.getByText("61%")).toBeInTheDocument();
    expect(screen.getByText(/based on 10 recent games/)).toBeInTheDocument();

    // Comfort and stretch section headings.
    expect(screen.getByText("Champions that fit how you play")).toBeInTheDocument();
    expect(screen.getByText("Worth trying")).toBeInTheDocument();

    // Comfort + stretch champion cards.
    expect(screen.getByText("Kaisa")).toBeInTheDocument();
    expect(screen.getByText("Xayah")).toBeInTheDocument();
    expect(screen.getByText("Draven")).toBeInTheDocument();
    expect(screen.getByText("Shen")).toBeInTheDocument();
    expect(screen.getByText("Janna")).toBeInTheDocument();

    // Stretch axis humanized, never raw snake_case, anywhere on the page.
    expect(screen.getAllByText(/objective focus/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/objective_focus/);
    expect(document.body.textContent).not.toMatch(/teamfight_vs_split/);

    // Disclaimer footer present.
    await waitFor(() => expect(screen.getByText(DISCLAIMER_TEXT)).toBeInTheDocument());
  });

  it("renders the exact backend 404 detail text and a link back to the report page", async () => {
    stubFetch(
      () =>
        ({
          ok: false,
          status: 404,
          json: async () => ({ detail: NOT_INDEXED_DETAIL }),
        }) as Response,
    );
    render(<ChampionsPage />);
    await submitRiotId("NeverAnalyzed#NA1");

    await waitFor(() => expect(screen.getByText(NOT_INDEXED_DETAIL)).toBeInTheDocument());
    const link = screen.getByRole("link", { name: /analyze a match to index this player/i });
    expect(link).toHaveAttribute("href", "/");
  });

  it("renders a retry-able error panel for non-404 failures", async () => {
    stubFetch(
      () =>
        ({
          ok: false,
          status: 500,
          json: async () => ({ detail: "boom" }),
        }) as Response,
    );
    render(<ChampionsPage />);
    await submitRiotId("Someone#NA1");

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
