import { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { SessionProvider, useSession } from "./session";
import * as api from "./api";
import { mockResult } from "./__fixtures__/mockResult";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    startAnalysis: vi.fn(),
    getChampionRecommendations: vi.fn(),
    getLedger: vi.fn(),
    getPool: vi.fn(),
  };
});

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}

function emit(es: FakeEventSource, payload: Record<string, unknown>) {
  act(() => {
    es.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.mocked(api.startAnalysis).mockResolvedValue({ job_id: "job1" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SessionProvider", () => {
  it("does not fan out to champions/ledger/pool until the analysis job reports done", async () => {
    vi.mocked(api.getChampionRecommendations).mockResolvedValue({ champions: [] } as never);
    vi.mocked(api.getLedger).mockResolvedValue({ entries: [] });
    vi.mocked(api.getPool).mockResolvedValue({ champions: [] });

    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.analyze("Player#NA1");
    });

    await waitFor(() => expect(api.startAnalysis).toHaveBeenCalledWith("Player#NA1"));
    expect(result.current.analysis.status).toBe("loading");
    expect(api.getChampionRecommendations).not.toHaveBeenCalled();
    expect(api.getLedger).not.toHaveBeenCalled();
    expect(api.getPool).not.toHaveBeenCalled();

    const es = FakeEventSource.instances.at(-1)!;
    emit(es, { stage: "narrating", progress: 0.8, message: "Narrating", status: "running", result: null, error: null });
    expect(api.getChampionRecommendations).not.toHaveBeenCalled();

    emit(es, { stage: "done", progress: 1, message: "Done", status: "done", result: mockResult, error: null });

    await waitFor(() => expect(result.current.analysis.status).toBe("done"));
    expect(result.current.analysis.result).toEqual(mockResult);
    expect(api.getChampionRecommendations).toHaveBeenCalledWith("Player#NA1");
    expect(api.getLedger).toHaveBeenCalledWith("Player#NA1");
    expect(api.getPool).toHaveBeenCalledWith("Player#NA1");
  });

  it("isolates resource failures -- one fan-out call failing does not block the others", async () => {
    vi.mocked(api.getChampionRecommendations).mockResolvedValue({ champions: [] } as never);
    vi.mocked(api.getLedger).mockRejectedValue(new Error("ledger boom"));
    vi.mocked(api.getPool).mockResolvedValue({ champions: [] });

    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.analyze("Player#NA1");
    });
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    emit(FakeEventSource.instances[0], { stage: "done", progress: 1, message: "Done", status: "done", result: mockResult, error: null });

    await waitFor(() => expect(result.current.ledger.status).toBe("error"));
    expect(result.current.ledger.error).toBe("ledger boom");
    await waitFor(() => expect(result.current.champions.status).toBe("done"));
    await waitFor(() => expect(result.current.pool.status).toBe("done"));
  });

  it("surfaces a job-level error without ever fanning out", async () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.analyze("Player#NA1");
    });
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    emit(FakeEventSource.instances[0], { stage: "fetching", progress: 0.1, message: "boom", status: "error", result: null, error: "No matches found" });

    await waitFor(() => expect(result.current.analysis.status).toBe("error"));
    expect(result.current.analysis.error).toBe("No matches found");
    expect(api.getChampionRecommendations).not.toHaveBeenCalled();
    expect(api.getLedger).not.toHaveBeenCalled();
    expect(api.getPool).not.toHaveBeenCalled();
  });
});
