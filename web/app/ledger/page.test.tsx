import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LedgerPage from "./page";
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

const LEDGER_RESPONSE = {
  entries: [
    { detector_key: "unspent_gold", title: "Sitting on gold", fired: 7, total: 9, rate: 0.7777777777777778 },
    { detector_key: "ward_drought", title: "Ward drought", fired: 1, total: 1, rate: null },
  ],
};

describe("LedgerPage", () => {
  it("shows only the form before anything has been fetched this session", () => {
    mockSession();
    render(<LedgerPage />);
    expect(screen.getByRole("heading", { name: "Ledger" })).toBeInTheDocument();
    expect(screen.queryByText("Sitting on gold")).not.toBeInTheDocument();
  });

  it("calls the shared analyze() on submit instead of fetching directly", async () => {
    const analyze = mockSession();
    render(<LedgerPage />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/gameName#tagLine/), "4DH#NA1");
    await user.click(screen.getByRole("button", { name: /show ledger/i }));
    expect(analyze).toHaveBeenCalledWith("4DH#NA1");
  });

  it("renders cached ledger data immediately when already fetched by another page", () => {
    mockSession({ riotId: "4DH#NA1", analysis: { ...idleAnalysis, status: "done" }, ledger: { status: "done", data: LEDGER_RESPONSE, error: null } });
    render(<LedgerPage />);
    expect(screen.getByText("Fired in 7/9 games (78%)")).toBeInTheDocument();
    expect(screen.getByText("1 game captured -- not enough data yet")).toBeInTheDocument();
  });

  it("shows the shared analysis progress message while the background job runs", () => {
    mockSession({ analysis: { status: "loading", progress: 0.5, stage: "narrating", message: "Asking Claude...", result: null, error: null } });
    render(<LedgerPage />);
    expect(screen.getByText(/Asking Claude/)).toBeInTheDocument();
  });

  it("shows a retry-able error panel when the ledger fetch failed", async () => {
    const analyze = mockSession({ ledger: { status: "error", data: null, error: "boom" } });
    render(<LedgerPage />);
    expect(screen.getByText("boom")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(analyze).toHaveBeenCalled();
  });
});
