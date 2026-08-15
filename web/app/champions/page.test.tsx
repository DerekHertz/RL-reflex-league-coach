import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChampionsPage from "./page";
import { useSession } from "@/lib/session";
import type { ChampionsResponse } from "@/lib/api";

vi.mock("@/lib/session", () => ({ useSession: vi.fn() }));

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

const NOT_INDEXED_DETAIL =
  "No indexed match history for this player yet. " +
  "Run POST /api/analysis first to fetch and index their recent matches, then retry.";

const CHAMPIONS_RESPONSE: ChampionsResponse = {
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
      rationale: "Evolving hybrid carry. Lines up with how you already play: teamfighting, aggression, farming.",
    },
    {
      champion: "Shen",
      roles: ["TOP"],
      fit_score: 0.71,
      kind: "stretch",
      matched_axes: ["farming"],
      stretch_axis: "objective_focus",
      rationale: "Stoic protector. A stretch pick: strong fit everywhere except objective focus.",
    },
  ],
  sample_size: 10,
};

const idleAnalysis = { status: "idle" as const, progress: 0, stage: "", message: "", result: null, error: null };
const idleResource = { status: "idle" as const, data: null, error: null };

function mockSession(overrides: Partial<ReturnType<typeof useSession>> = {}) {
  const analyze = vi.fn();
  vi.mocked(useSession).mockReturnValue({
    riotId: "",
    analysis: idleAnalysis,
    champions: idleResource,
    ledger: idleResource,
    pool: idleResource,
    analyze,
    ...overrides,
  });
  return analyze;
}

function stubMetaFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }) }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ChampionsPage -- shared session (Any role, the default)", () => {
  beforeEach(stubMetaFetch);

  it("shows only the form before anything has been fetched this session", () => {
    mockSession();
    render(<ChampionsPage />);
    expect(screen.getByText("Champion fit")).toBeInTheDocument();
    expect(screen.queryByText("Kaisa")).not.toBeInTheDocument();
  });

  it("calls the shared analyze() on submit, not a direct fetch", async () => {
    const analyze = mockSession();
    render(<ChampionsPage />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/gameName#tagLine/), "4DH#NA1");
    await user.click(screen.getByRole("button", { name: /find champions/i }));
    expect(analyze).toHaveBeenCalledWith("4DH#NA1");
  });

  it("renders cached recommendations immediately when already fetched by another page", () => {
    mockSession({ riotId: "4DH#NA1", analysis: { ...idleAnalysis, status: "done" }, champions: { status: "done", data: CHAMPIONS_RESPONSE, error: null } });
    render(<ChampionsPage />);
    expect(screen.getByText("Kaisa")).toBeInTheDocument();
    expect(screen.getByText("Shen")).toBeInTheDocument();
  });

  it("shows the shared analysis progress message while the background job runs", () => {
    mockSession({ analysis: { status: "loading", progress: 0.5, stage: "narrating", message: "Asking Claude...", result: null, error: null } });
    render(<ChampionsPage />);
    expect(screen.getByText(/Asking Claude/)).toBeInTheDocument();
  });

  it("shows a retry-able error panel when the shared champions fetch failed", async () => {
    const analyze = mockSession({ champions: { status: "error", data: null, error: "boom" } });
    render(<ChampionsPage />);
    expect(screen.getByText("boom")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(analyze).toHaveBeenCalled();
  });
});

describe("ChampionsPage -- role filter (direct fetch, layered on top of the shared default)", () => {
  beforeEach(() => {
    stubMetaFetch();
    mockSession({ riotId: "4DH#NA1", analysis: { ...idleAnalysis, status: "done" }, champions: { status: "done", data: CHAMPIONS_RESPONSE, error: null } });
  });

  async function submitWithRole(id: string, role: string) {
    const user = userEvent.setup();
    const input = screen.getByPlaceholderText(/gameName#tagLine/);
    await user.clear(input);
    await user.type(input, id);
    await user.selectOptions(screen.getByRole("combobox"), role);
    await user.click(screen.getByRole("button", { name: /find champions/i }));
  }

  it("does not call the shared analyze() -- fetches /api/champions directly with the role", async () => {
    const fetchMock = vi.fn<typeof fetch>((input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/meta")) {
        return Promise.resolve({ ok: true, json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }) } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => CHAMPIONS_RESPONSE } as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ChampionsPage />);
    await submitWithRole("4DH#NA1", "UTILITY");

    await waitFor(() => expect(screen.getByText("Kaisa")).toBeInTheDocument());
    const championsCall = fetchMock.mock.calls.find((c) => (c[0] as string).toString().includes("/api/champions"));
    expect(championsCall).toBeTruthy();
    expect(JSON.parse((championsCall![1] as RequestInit).body as string)).toEqual({ riot_id: "4DH#NA1", role: "UTILITY" });
  });

  it("renders the exact backend 404 detail text and a link back to the report page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/api/meta")) {
          return Promise.resolve({ ok: true, json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }) } as Response);
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({ detail: NOT_INDEXED_DETAIL }) } as Response);
      }),
    );
    render(<ChampionsPage />);
    await submitWithRole("NeverAnalyzed#NA1", "TOP");

    await waitFor(() => expect(screen.getByText(NOT_INDEXED_DETAIL)).toBeInTheDocument());
    const link = screen.getByRole("link", { name: /analyze a match to index this player/i });
    expect(link).toHaveAttribute("href", "/");
  });
});
