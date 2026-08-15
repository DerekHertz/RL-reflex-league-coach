import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnalysisProgress } from "./AnalysisProgress";
import { useSession } from "@/lib/session";

vi.mock("@/lib/session", () => ({ useSession: vi.fn() }));

describe("AnalysisProgress", () => {
  it("renders nothing when no analysis is running", () => {
    vi.mocked(useSession).mockReturnValue({
      riotId: "",
      analysis: { status: "idle", progress: 0, stage: "", message: "", result: null, error: null },
      champions: { status: "idle", data: null, error: null },
      ledger: { status: "idle", data: null, error: null },
      pool: { status: "idle", data: null, error: null },
      analyze: vi.fn(),
    });
    const { container } = render(<AnalysisProgress />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the shared analysis message while loading", () => {
    vi.mocked(useSession).mockReturnValue({
      riotId: "Player#NA1",
      analysis: { status: "loading", progress: 0.5, stage: "narrating", message: "Asking Claude for coaching narration...", result: null, error: null },
      champions: { status: "idle", data: null, error: null },
      ledger: { status: "idle", data: null, error: null },
      pool: { status: "idle", data: null, error: null },
      analyze: vi.fn(),
    });
    render(<AnalysisProgress />);
    expect(screen.getByText(/Asking Claude for coaching narration/)).toBeInTheDocument();
  });
});
