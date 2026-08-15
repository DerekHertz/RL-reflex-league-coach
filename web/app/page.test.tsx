import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "./page";
import { useSession } from "@/lib/session";
import { mockResult } from "@/lib/__fixtures__/mockResult";

vi.mock("@/lib/session", () => ({ useSession: vi.fn() }));

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

const idleAnalysis = { status: "idle" as const, progress: 0, stage: "", message: "", result: null, error: null };

function mockSession(overrides: Partial<ReturnType<typeof useSession>> = {}) {
  const analyze = vi.fn();
  vi.mocked(useSession).mockReturnValue({
    riotId: "",
    analysis: idleAnalysis,
    champions: { status: "idle", data: null, error: null },
    ledger: { status: "idle", data: null, error: null },
    pool: { status: "idle", data: null, error: null },
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

describe("Home", () => {
  it("does not call analyze for a Riot ID missing the '#' separator", async () => {
    const analyze = mockSession();
    render(<Home />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/gameName#tagLine/), "NotARiotId");
    await user.click(screen.getByRole("button", { name: /analyze/i }));

    expect(analyze).not.toHaveBeenCalled();
    expect(screen.getByText(/Enter a Riot ID as gameName#tagLine/)).toBeInTheDocument();
  });

  it("calls analyze with the entered Riot ID on submit", async () => {
    const analyze = mockSession();
    render(<Home />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/gameName#tagLine/), "Player#NA1");
    await user.click(screen.getByRole("button", { name: /analyze/i }));

    expect(analyze).toHaveBeenCalledWith("Player#NA1");
  });

  it("shows progress while the shared analysis is loading", () => {
    mockSession({ analysis: { status: "loading", progress: 0.5, stage: "narrating", message: "Asking Claude...", result: null, error: null } });
    render(<Home />);
    expect(screen.getByText(/narrating/)).toBeInTheDocument();
  });

  it("renders the shared analysis result once done", () => {
    mockSession({ analysis: { status: "done", progress: 1, stage: "done", message: "Done", result: mockResult, error: null } });
    render(<Home />);
    expect(screen.getByText(mockResult.narrative.headline)).toBeInTheDocument();
  });

  it("shows a retry-able error panel when the shared analysis failed", async () => {
    const analyze = mockSession({ analysis: { status: "error", progress: 0, stage: "", message: "", result: null, error: "boom" } });
    render(<Home />);
    expect(screen.getByText("boom")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(analyze).toHaveBeenCalled();
  });
});
