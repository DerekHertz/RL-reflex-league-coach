import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PoolPage from "./page";
import { useSession } from "@/lib/session";

vi.mock("@/lib/session", () => ({ useSession: vi.fn() }));

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

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

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }) }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

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

describe("PoolPage", () => {
  it("shows only the form before anything has been fetched this session", () => {
    mockSession();
    render(<PoolPage />);
    expect(screen.getByRole("heading", { name: "Your pool" })).toBeInTheDocument();
    expect(screen.queryByText("Annie")).not.toBeInTheDocument();
  });

  it("calls the shared analyze() on submit instead of fetching directly", async () => {
    const analyze = mockSession();
    render(<PoolPage />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/gameName#tagLine/), "4DH#NA1");
    await user.click(screen.getByRole("button", { name: /show my pool/i }));
    expect(analyze).toHaveBeenCalledWith("4DH#NA1");
  });

  it("renders cached pool data immediately -- unlocked champion's entries and a locked champion's message", () => {
    mockSession({ riotId: "4DH#NA1", analysis: { ...idleAnalysis, status: "done" }, pool: { status: "done", data: POOL_RESPONSE, error: null } });
    render(<PoolPage />);

    expect(screen.getByText("Fired in 3/5 games (60%)")).toBeInTheDocument();
    expect(screen.getByText("2 games captured -- not enough data yet")).toBeInTheDocument();
    expect(screen.getByText("Ahri")).toBeInTheDocument();
    expect(screen.getByText("1 more game to unlock this champion's stats")).toBeInTheDocument();
    expect(screen.queryByText("Fired in 1/2 games")).not.toBeInTheDocument();
  });

  it("shows the shared analysis progress message while the background job runs", () => {
    mockSession({ analysis: { status: "loading", progress: 0.5, stage: "narrating", message: "Asking Claude...", result: null, error: null } });
    render(<PoolPage />);
    expect(screen.getByText(/Asking Claude/)).toBeInTheDocument();
  });

  it("shows a retry-able error panel when the pool fetch failed", async () => {
    const analyze = mockSession({ pool: { status: "error", data: null, error: "boom" } });
    render(<PoolPage />);
    expect(screen.getByText("boom")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(analyze).toHaveBeenCalled();
  });
});
