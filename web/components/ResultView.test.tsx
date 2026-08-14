import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ResultView } from "./ResultView";
import { mockResult } from "@/lib/__fixtures__/mockResult";

const DISCLAIMER_TEXT =
  "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games " +
  "or anyone officially involved in producing or managing Riot Games properties.";

// "rank N/10" is required by the spec (comparison basis on every metric).
// What's forbidden is competitive-ladder "rank" -- Gold rank, Diamond tier,
// etc -- so only flag "rank" when it's NOT immediately followed by a number.
const FORBIDDEN_PATTERNS = [/\bMMR\b/i, /\btier\b/i, /\brank\b(?!\s*\d)/i, /\bLP\b/i, /\belo\b/i];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ disclaimer: DISCLAIMER_TEXT, engine_version: "test" }),
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ResultView", () => {
  it("renders the finding, the clean check, and the null lane_opponent case without crashing", () => {
    render(<ResultView result={mockResult} />);

    // Finding present.
    expect(screen.getByText("Time spent dead")).toBeInTheDocument();
    // Clean check present.
    expect(screen.getByText("Sitting on gold")).toBeInTheDocument();
    // lane_opponent is null -- no "vs" text should appear in the header meta.
    expect(screen.queryByText(/vs /)).not.toBeInTheDocument();
  });

  it("renders narration in headline -> what-went-well -> findings -> closing order", () => {
    const { container } = render(<ResultView result={mockResult} />);
    const text = container.textContent ?? "";
    const headlineIdx = text.indexOf(mockResult.narrative.headline);
    const wentWellIdx = text.indexOf(mockResult.narrative.what_went_well[0]);
    const findingIdx = text.indexOf("Time spent dead");
    const closingIdx = text.indexOf(mockResult.narrative.closing);

    expect(headlineIdx).toBeGreaterThanOrEqual(0);
    expect(wentWellIdx).toBeGreaterThan(headlineIdx);
    expect(findingIdx).toBeGreaterThan(wentWellIdx);
    expect(closingIdx).toBeGreaterThan(findingIdx);
  });

  it("fetches and renders the live disclaimer text rather than hardcoding it", async () => {
    render(<ResultView result={mockResult} />);
    await waitFor(() => expect(screen.getByText(DISCLAIMER_TEXT)).toBeInTheDocument());
  });

  it("renders the cannot-see panel", () => {
    render(<ResultView result={mockResult} />);
    expect(screen.getByText("What I cannot see")).toBeInTheDocument();
  });

  it("renders the provenance line with model and elapsed time", () => {
    render(<ResultView result={mockResult} />);
    expect(screen.getByText(/Narrated by Claude/)).toBeInTheDocument();
    expect(screen.getByText(/claude-opus-5/)).toBeInTheDocument();
    expect(screen.getByText(/8\.4s/)).toBeInTheDocument();
  });

  it("never introduces forbidden rank/tier/MMR language in our own static copy", () => {
    const { container } = render(<ResultView result={mockResult} />);
    // Strip out the dynamic narrative/fact-sheet text (backend-guarded, not
    // our concern here) and check only the component-authored chrome: the
    // eyebrows, captions, and labels we wrote ourselves.
    const staticCopyNodes = container.querySelectorAll(
      '[class*="eyebrow"], [class*="caption"], [class*="railEyebrow"]',
    );
    const staticCopy = Array.from(staticCopyNodes)
      .map((n) => n.textContent ?? "")
      .join(" ");
    for (const pattern of FORBIDDEN_PATTERNS) {
      expect(staticCopy).not.toMatch(pattern);
    }
  });
});
