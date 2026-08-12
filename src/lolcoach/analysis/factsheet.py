"""MatchFactSheet -- the anonymization boundary between the analysis engine
and Claude.

The pydantic models below structurally cannot carry identity: there is no
field anywhere in this schema for a puuid, Riot ID, summoner name, or match
ID (a match ID plus a champion narrows to a real account, so it's excluded
too).

This module is PURE SCHEMA -- no imports from `lolcoach.domain`,
`lolcoach.riot`, or `lolcoach.detectors`. That's deliberate and enforced by
tests/contract/test_llm_boundary.py: `lolcoach.llm` imports this module (for
the `MatchFactSheet` type and `NOT_KNOWABLE`), and if this module pulled in
`lolcoach.domain` transitively, so would every LLM call site. The function
that actually BUILDS a sheet from an AnalysisContext (and therefore needs
those imports) lives in `lolcoach.analysis.build`, which `lolcoach.llm` never
imports.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

NOT_KNOWABLE: tuple[str, ...] = (
    "Ward placement locations -- the API reports ward events without coordinates. "
    "You may discuss ward counts, types, and timing gaps, never where wards were placed.",
    "Positioning between minute marks -- position samples exist only once per minute. "
    "Never describe movement, rotations, or pathing between samples.",
    "Teamfight spacing, ability usage, dodges, animation cancels, or mechanical execution.",
    "Whether a death was intentional (bait, trade, sacrifice) or a mistake.",
    "Communication, pings, premade status, or teammate intent.",
    "Exact recall timings -- backs are inferred from item-purchase clustering and are approximate.",
    "Champion matchup difficulty, patch balance, or which champion 'should' win a lane.",
    "The player's rank, MMR, LP, or skill relative to anyone outside this match.",
)


class SubjectFacts(BaseModel):
    champion: str
    role: str


class OpponentFacts(BaseModel):
    champion: str
    role: str


class MatchMeta(BaseModel):
    queue_name: str
    patch: str
    duration: str
    result: Literal["win", "loss"]
    team_side: Literal["blue", "red"]


class MetricComparison(BaseModel):
    peer: Literal["lane_opponent", "role_cohort_avg"]
    peer_value: float
    delta: float
    rank_in_lobby: int | None = None


class MetricFact(BaseModel):
    id: str
    label: str
    value: float
    unit: Literal["gold", "seconds", "percent", "count", "ratio", "per_minute"]
    direction: Literal["higher_better", "lower_better", "neutral"]
    comparisons: list[MetricComparison] = []


class EvidenceFact(BaseModel):
    label: str
    value: float
    unit: str
    peer_value: float | None = None
    peer_label: str | None = None


class FindingFact(BaseModel):
    id: str
    title: str
    severity: Literal["info", "minor", "moderate", "major"]
    phase: Literal["early", "mid", "late", "whole_game"]
    confidence: float
    what_happened: str
    timestamps: list[str]
    evidence: list[EvidenceFact]
    map_regions: list[str] = []


class CleanCheck(BaseModel):
    id: str
    title: str
    evidence: list[EvidenceFact] = []


class SkippedCheck(BaseModel):
    check: str
    reason: str


class SkillScore(BaseModel):
    skill: Literal["laning", "economy", "survivability", "vision", "objectives", "teamfighting"]
    band: Literal["below_lobby", "at_lobby", "above_lobby"]
    basis: list[str]


class MatchFactSheet(BaseModel):
    schema_version: Literal[1] = 1
    subject: SubjectFacts
    match: MatchMeta
    lane_opponent: OpponentFacts | None
    metrics: list[MetricFact]
    findings: list[FindingFact]
    clean_checks: list[CleanCheck]
    skipped_checks: list[SkippedCheck]
    skill_scores: list[SkillScore]
    not_knowable: list[str]
