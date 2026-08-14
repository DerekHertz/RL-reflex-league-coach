// Hand-built fixture, not a snapshot of a live API call. The shape and prose
// are lifted from a real cached analysis run (Anivia, NA1_5613973325) so the
// numbers read like something Claude would actually say, but this file is
// static and must be kept in sync with lib/api.ts by hand.
//
// Deliberately exercises: a finding, a clean check, lane_opponent === null,
// a metric with a peer comparison (ranked) alongside metrics with none (the
// "no peer comparison available" path), and a non-empty not_knowable list
// long enough to trigger the CannotSeePanel collapse/expand toggle.

import { AnalysisResult } from "@/lib/api";

export const mockResult: AnalysisResult = {
  puuid: "ugKFRrtm6AoTC0eYktWG9897TeaK9L9loF97D6FGVcVe644rWWNn1rutEj28Ds8OCSPleOIvLlbU7Q",
  match_id: "NA1_5613973325",
  other_match_ids: [],
  fact_sheet: {
    subject: { champion: "Anivia", role: "unknown" },
    match: {
      queue_name: "Queue 1750",
      patch: "16.15",
      duration: "29:18",
      result: "win",
      team_side: "blue",
    },
    lane_opponent: null,
    metrics: [
      {
        id: "gold_per_minute",
        label: "Gold per minute",
        value: 839,
        unit: "per_minute",
        direction: "higher_better",
        comparisons: [
          { peer: "role_cohort_avg", peer_value: 610, delta: 229, rank_in_lobby: 2 },
        ],
      },
      {
        id: "cs_per_minute",
        label: "CS per minute",
        value: 0,
        unit: "per_minute",
        direction: "higher_better",
        comparisons: [],
      },
      {
        id: "time_dead_share",
        label: "Share of game spent dead",
        value: 56.3,
        unit: "percent",
        direction: "lower_better",
        comparisons: [],
      },
    ],
    findings: [
      {
        id: "time_dead:0",
        title: "Time spent dead",
        severity: "major",
        phase: "whole_game",
        confidence: 1,
        what_happened: "56.3% of the game was spent dead, across 9 deaths.",
        timestamps: ["22:21"],
        evidence: [
          {
            label: "Share of game spent dead",
            value: 56.3,
            unit: "percent",
            peer_value: null,
            peer_label: "role_cohort",
          },
          { label: "Number of deaths", value: 9, unit: "count", peer_value: null, peer_label: null },
          {
            label: "Share of death-time cost from after 20 minutes",
            value: 47.9,
            unit: "percent",
            peer_value: null,
            peer_label: null,
          },
        ],
      },
    ],
    clean_checks: [
      {
        id: "unspent_gold",
        title: "Sitting on gold",
        evidence: [
          {
            label: "Minutes spent over 1400 unspent gold",
            value: 1,
            unit: "count",
            peer_value: null,
            peer_label: null,
          },
          { label: "Peak unspent gold", value: 3009, unit: "gold", peer_value: null, peer_label: null },
        ],
      },
    ],
    skipped_checks: [{ check: "Lost a lane lead", reason: "no lane opponent: teamPosition unavailable" }],
    skill_scores: [
      { skill: "economy", band: "at_lobby", basis: ["unspent_gold"] },
      { skill: "survivability", band: "below_lobby", basis: ["time_dead"] },
    ],
    not_knowable: [
      "Ward placement locations -- the API reports ward events without coordinates. You may discuss ward counts, types, and timing gaps, never where wards were placed.",
      "Positioning between minute marks -- position samples exist only once per minute. Never describe movement, rotations, or pathing between samples.",
      "Teamfight spacing, ability usage, dodges, animation cancels, or mechanical execution.",
      "Whether a death was intentional (bait, trade, sacrifice) or a mistake.",
      "Communication, pings, premade status, or teammate intent.",
      "Exact recall timings -- backs are inferred from item-purchase clustering and are approximate.",
      "Champion matchup difficulty, patch balance, or which champion 'should' win a lane.",
      "The player's rank, MMR, LP, or skill relative to anyone outside this match.",
    ],
  },
  narrative: {
    headline: "A win on Anivia, but over half the game was spent watching from the grey screen",
    what_went_well: [
      "Your gold didn't sit idle — you only spent 1 minute above the unspent-gold threshold this game, so purchases were going down close to when you could afford them, even with a peak of 3009 gold on hand at one point.",
    ],
    focus_areas: ["time_dead:0"],
    narrations: [
      {
        finding_id: "time_dead:0",
        explanation:
          "You were dead for 56.3% of the match across 9 deaths, and 47.9% of that lost time came from the later portion of the game where respawn timers are longest. Anivia's value comes from being on the map with Wall and ult up, and you simply weren't there for most of it — including the death at 22:21.",
        fix: "Treat each late-game death as a much larger cost than an early one: before committing to a fight past the mid-game, check that your escape option (Wall or Flash) is available, and if it isn't, hold your position and let the fight come to your range instead.",
        drill:
          "For your next three games, note the clock at each death. Any death after the mid-game gets written down with what was on cooldown at the time. If Wall was down for most of them, you're spending it too early in the fight — start holding it for the disengage instead of the engage.",
      },
    ],
    closing:
      "You won this one, and your item timings were tidy. Cut the late-game deaths and you'll be on the map for the fights you're currently missing.",
  },
  used_fallback: false,
  model: "claude-opus-5",
  elapsed_s: 8.4,
};
