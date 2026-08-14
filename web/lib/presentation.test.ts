import { describe, expect, it } from "vitest";
import {
  bandColorVar,
  bandLabel,
  fetchProgressLabel,
  findingHeadTintOpacity,
  formatEvidenceValue,
  formatNumber,
  formatTimestamps,
  peerLabel,
  rankTercile,
  rankTercileColorVar,
  resultLabel,
  severityColorVar,
  severityLabel,
} from "./presentation";

describe("severityColorVar", () => {
  it("maps major to the major severity var", () => {
    expect(severityColorVar("major")).toBe("var(--sev-major)");
  });
  it("maps moderate to the moderate severity var", () => {
    expect(severityColorVar("moderate")).toBe("var(--sev-moderate)");
  });
  it("maps minor to the minor severity var", () => {
    expect(severityColorVar("minor")).toBe("var(--sev-minor)");
  });
  it("falls back unknown/info severities to the minor var", () => {
    expect(severityColorVar("info")).toBe("var(--sev-minor)");
    expect(severityColorVar("bogus")).toBe("var(--sev-minor)");
  });
});

describe("severityLabel", () => {
  it("renders the word for every branch, never color-only", () => {
    expect(severityLabel("major")).toBe("MAJOR");
    expect(severityLabel("moderate")).toBe("MODERATE");
    expect(severityLabel("minor")).toBe("MINOR");
    expect(severityLabel("info")).toBe("MINOR");
  });
});

describe("findingHeadTintOpacity", () => {
  it("is 0.07 for major", () => {
    expect(findingHeadTintOpacity("major")).toBe(0.07);
  });
  it("is 0.09 for moderate", () => {
    expect(findingHeadTintOpacity("moderate")).toBe(0.09);
  });
  it("is 0 (no tint) for minor", () => {
    expect(findingHeadTintOpacity("minor")).toBe(0);
  });
  it("is 0 for unrecognized severities", () => {
    expect(findingHeadTintOpacity("info")).toBe(0);
  });
});

describe("bandLabel", () => {
  it("covers below_lobby", () => {
    expect(bandLabel("below_lobby")).toBe("BELOW LOBBY");
  });
  it("covers at_lobby", () => {
    expect(bandLabel("at_lobby")).toBe("AT LOBBY");
  });
  it("covers above_lobby even though v1 never emits it", () => {
    expect(bandLabel("above_lobby")).toBe("ABOVE LOBBY");
  });
});

describe("bandColorVar", () => {
  it("below_lobby is the bad color", () => {
    expect(bandColorVar("below_lobby")).toBe("var(--bad)");
  });
  it("at_lobby is neutral ink, not a severity color", () => {
    expect(bandColorVar("at_lobby")).toBe("var(--ink-400)");
  });
  it("above_lobby is the good color", () => {
    expect(bandColorVar("above_lobby")).toBe("var(--good)");
  });
});

describe("rankTercile", () => {
  it("ranks 1-3 of 10 are good (top third)", () => {
    expect(rankTercile(1)).toBe("good");
    expect(rankTercile(3)).toBe("good");
  });
  it("ranks 4-7 of 10 are mid (middle third)", () => {
    expect(rankTercile(4)).toBe("mid");
    expect(rankTercile(7)).toBe("mid");
  });
  it("ranks 8-10 of 10 are bad (bottom third)", () => {
    expect(rankTercile(8)).toBe("bad");
    expect(rankTercile(10)).toBe("bad");
  });
});

describe("rankTercileColorVar", () => {
  it("maps every tercile to its raw token", () => {
    expect(rankTercileColorVar("good")).toBe("var(--jade-600)");
    expect(rankTercileColorVar("mid")).toBe("var(--gold-500)");
    expect(rankTercileColorVar("bad")).toBe("var(--red-600)");
  });
});

describe("peerLabel", () => {
  it("labels lane_opponent", () => {
    expect(peerLabel("lane_opponent")).toBe("lane opponent");
  });
  it("labels role_cohort_avg", () => {
    expect(peerLabel("role_cohort_avg")).toBe("role cohort");
  });
});

describe("resultLabel", () => {
  it("win is VICTORY", () => {
    expect(resultLabel("win")).toBe("VICTORY");
  });
  it("loss is DEFEAT", () => {
    expect(resultLabel("loss")).toBe("DEFEAT");
  });
});

describe("formatNumber", () => {
  it("renders integers bare", () => {
    expect(formatNumber(9)).toBe("9");
  });
  it("renders non-integers to one decimal", () => {
    expect(formatNumber(56.3)).toBe("56.3");
  });
});

describe("formatEvidenceValue", () => {
  it("appends % for percent", () => {
    expect(formatEvidenceValue(56.3, "percent")).toBe("56.3%");
  });
  it("thousands-separates gold with no suffix", () => {
    expect(formatEvidenceValue(3009, "gold")).toBe("3,009");
  });
  it("leaves count as a plain number", () => {
    expect(formatEvidenceValue(9, "count")).toBe("9");
  });
  it("appends the raw unit name for anything else", () => {
    expect(formatEvidenceValue(839, "per_minute")).toBe("839 per_minute");
  });
});

describe("fetchProgressLabel", () => {
  it("parses a 'Fetching match n/total' backend message into a terse status line", () => {
    expect(fetchProgressLabel("Fetching match 3/5: NA1_5613973325")).toBe("pulling 3/5 matches");
  });
  it("falls back to the raw message when it doesn't match the expected shape", () => {
    expect(fetchProgressLabel("Narrating with Claude...")).toBe("Narrating with Claude...");
  });
});

describe("formatTimestamps", () => {
  it("returns null for an empty list", () => {
    expect(formatTimestamps([])).toBeNull();
  });
  it("returns the bare value for a single timestamp", () => {
    expect(formatTimestamps(["22:21"])).toBe("22:21");
  });
  it("returns a first-last range for multiple timestamps", () => {
    expect(formatTimestamps(["18:00", "24:00"])).toBe("18:00 – 24:00");
  });
});
