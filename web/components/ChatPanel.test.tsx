import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";
import { mockResult } from "@/lib/__fixtures__/mockResult";

const { fact_sheet: sheet, narrative } = mockResult;

function stubFetch(chatHandler: () => Promise<Response> | Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/chat")) {
        return Promise.resolve(chatHandler());
      }
      throw new Error(`unexpected fetch to ${url}`);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function askQuestion(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByPlaceholderText(/why did the ward drought/i), question);
  await user.click(screen.getByRole("button", { name: /ask/i }));
}

describe("ChatPanel", () => {
  it("renders the ask form with no prior turns", () => {
    render(<ChatPanel sheet={sheet} narrative={narrative} />);
    expect(screen.getByText("Ask about this match")).toBeInTheDocument();
    expect(screen.queryByText(/Q:/)).not.toBeInTheDocument();
  });

  it("sends the question and prior history, then appends the answer to the turn list", async () => {
    let capturedBody: unknown = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        capturedBody = init?.body ? JSON.parse(init.body as string) : null;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: "It fired because your first ward went down after 4 minutes.",
            cited_finding_ids: [],
            used_fallback: false,
          }),
        } as Response);
      }),
    );

    render(<ChatPanel sheet={sheet} narrative={narrative} />);
    await askQuestion("Why did ward drought fire?");

    await waitFor(() =>
      expect(screen.getByText("It fired because your first ward went down after 4 minutes.")).toBeInTheDocument(),
    );
    expect(screen.getByText("Why did ward drought fire?")).toBeInTheDocument();

    expect(capturedBody).toMatchObject({
      fact_sheet: sheet,
      narrative,
      question: "Why did ward drought fire?",
      history: [],
    });

    // Second question resends the first turn as history.
    await askQuestion("What should I do differently?");
    await waitFor(() => expect(screen.getByText("What should I do differently?")).toBeInTheDocument());
    expect(capturedBody).toMatchObject({
      history: [{ question: "Why did ward drought fire?", answer: "It fired because your first ward went down after 4 minutes." }],
    });
  });

  it("shows an inline error and does not clear the input on failure", async () => {
    stubFetch(() => ({ ok: false, status: 500, json: async () => ({ detail: "boom" }) }) as Response);
    render(<ChatPanel sheet={sheet} narrative={narrative} />);
    await askQuestion("Why did ward drought fire?");

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
    expect(screen.getByPlaceholderText(/why did the ward drought/i)).toHaveValue("Why did ward drought fire?");
  });

  it("does not submit an empty or whitespace-only question", async () => {
    stubFetch(() => ({ ok: true, json: async () => ({ answer: "", cited_finding_ids: [], used_fallback: false }) }) as Response);
    render(<ChatPanel sheet={sheet} narrative={narrative} />);
    expect(screen.getByRole("button", { name: /ask/i })).toBeDisabled();
  });
});
