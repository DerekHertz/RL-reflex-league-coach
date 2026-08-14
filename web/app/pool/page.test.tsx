import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PoolPage from "./page";

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

const NOT_INDEXED_DETAIL =
  "No indexed match history for this player yet. " +
  "Run POST /api/analysis first to fetch and index their recent matches, then retry.";

const POOL_RESPONSE = {
  champions: [
    {
      champion_id: 1,
      champion_name: "Annie",
      games_played: 5,
      entries: [
        { detector_key: "unspent_gold", title: "Sitting on gold", fired: 3, total: 5, rate: 0.6 },
        { detector_key: "ward_drought", title: "Ward drought", fired: 1, total: 2, rate: null },
      ],
    },
    {
      champion_id: 2,
      champion_name: "Ahri",
      games_played: 2,
      entries: [{ detector_key: "unspent_gold", title: "Sitting on gold", fired: 1, total: 2, rate: null }],
    },
  ],
};

function stubFetch(poolHandler: () => Promise<Response> | Response) {
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
      if (url.includes("/api/pool")) {
        return Promise.resolve(poolHandler());
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
  await user.click(screen.getByRole("button", { name: /show my pool/i }));
}

describe("PoolPage", () => {
  beforeEach(() => {
    stubFetch(() => ({ ok: true, json: async () => POOL_RESPONSE }) as Response);
  });

  it("shows only the form before any submission", () => {
    render(<PoolPage />);
    expect(screen.getByRole("heading", { name: "Your pool" })).toBeInTheDocument();
    expect(screen.queryByText("Annie")).not.toBeInTheDocument();
  });

  it("renders an unlocked champion's entries and a locked champion's message", async () => {
    render(<PoolPage />);
    await submitRiotId("4DH#NA1");

    await waitFor(() => expect(screen.getByText("Annie")).toBeInTheDocument());
    expect(screen.getByText("Fired in 3/5 games (60%)")).toBeInTheDocument();
    expect(screen.getByText("2 games captured -- not enough data yet")).toBeInTheDocument();

    expect(screen.getByText("Ahri")).toBeInTheDocument();
    expect(screen.getByText("1 more game to unlock this champion's stats")).toBeInTheDocument();
    // Locked champion's entries are never rendered, even though the API returned them.
    expect(screen.queryByText("Fired in 1/2 games")).not.toBeInTheDocument();

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
    render(<PoolPage />);
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
    render(<PoolPage />);
    await submitRiotId("Someone#NA1");

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
