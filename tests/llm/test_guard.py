"""Offline guard tests -- hand-crafted bad responses, no live API calls.
These are the tests that catch a hallucinated number before it ever ships.
"""

from __future__ import annotations

from lolcoach.analysis.factsheet import (
    CleanCheck,
    EvidenceFact,
    FindingFact,
    MatchFactSheet,
    MatchMeta,
    MetricFact,
    SubjectFacts,
)
from lolcoach.llm.guard import NumberProvenanceGuard
from lolcoach.llm.schemas import CoachingResponse, FindingNarration


def _sheet() -> MatchFactSheet:
    return MatchFactSheet(
        subject=SubjectFacts(champion="Brand", role="UTILITY"),
        match=MatchMeta(queue_name="Ranked Solo/Duo", patch="16.2", duration="29:00", result="win", team_side="red"),
        lane_opponent=None,
        metrics=[
            MetricFact(id="gold_per_minute", label="Gold per minute", value=340.0, unit="per_minute", direction="higher_better", comparisons=[]),
        ],
        findings=[
            FindingFact(
                id="unspent_gold:0",
                title="Sitting on gold",
                severity="moderate",
                phase="mid",
                confidence=1.0,
                what_happened="Gold reached 2200 and stayed above 1400 for about 4.0 minutes.",
                timestamps=["12:00", "16:00"],
                evidence=[
                    EvidenceFact(label="Peak gold held", value=2200.0, unit="gold"),
                    EvidenceFact(label="Minutes held above threshold", value=4.0, unit="count"),
                ],
            )
        ],
        clean_checks=[CleanCheck(id="time_dead", title="Time spent dead", evidence=[])],
        skipped_checks=[],
        skill_scores=[],
        not_knowable=["Ward placement locations."],
    )


def _valid_response() -> CoachingResponse:
    return CoachingResponse(
        headline="Your biggest lever this game was gold efficiency.",
        what_went_well=["Time spent dead stayed in a healthy range."],
        focus_areas=["unspent_gold:0"],
        narrations=[
            FindingNarration(
                finding_id="unspent_gold:0",
                explanation="Gold reached 2200 and sat unspent for 4.0 minutes around 12:00.",
                fix="Spend down to a partial component the moment you're back at base.",
            )
        ],
        closing="Fix the back-timing and the rest of your game looked solid.",
    )


def test_valid_response_has_no_violations() -> None:
    sheet = _sheet()
    violations = NumberProvenanceGuard(sheet).check(_valid_response())
    assert violations == []


def test_invented_number_is_caught() -> None:
    sheet = _sheet()
    bad = _valid_response()
    bad.narrations[0].explanation = "Gold reached 3750 and sat unspent."
    violations = NumberProvenanceGuard(sheet).check(bad)
    assert any(v.kind == "unknown_number" and v.detail == "3750" for v in violations)


def test_dangling_finding_id_in_focus_areas_is_caught() -> None:
    sheet = _sheet()
    bad = _valid_response()
    bad.focus_areas = ["death_regions:0"]  # not a real finding on this sheet
    violations = NumberProvenanceGuard(sheet).check(bad)
    assert any(v.kind == "unknown_finding_id" and v.detail == "death_regions:0" for v in violations)


def test_dangling_finding_id_in_narration_is_caught() -> None:
    sheet = _sheet()
    bad = _valid_response()
    bad.narrations[0].finding_id = "made_up:0"
    violations = NumberProvenanceGuard(sheet).check(bad)
    assert any(v.kind == "unknown_finding_id" and v.detail == "made_up:0" for v in violations)


def test_rank_assertion_is_caught() -> None:
    sheet = _sheet()
    bad = _valid_response()
    bad.closing = "Honestly this reads like Platinum-level decision making."
    violations = NumberProvenanceGuard(sheet).check(bad)
    assert any(v.kind == "forbidden_term" and v.detail.lower() == "platinum" for v in violations)


def test_mmr_reference_is_caught() -> None:
    sheet = _sheet()
    bad = _valid_response()
    bad.headline = "Your MMR probably doesn't reflect this performance."
    violations = NumberProvenanceGuard(sheet).check(bad)
    assert any(v.kind == "forbidden_term" for v in violations)


def test_currency_word_gold_is_not_flagged_as_rank_term() -> None:
    # "gold" is the game's own currency name -- must never be treated as a
    # forbidden rank-tier reference, or almost every legitimate response fails.
    sheet = _sheet()
    response = _valid_response()
    response.closing = "You banked plenty of gold this game, just spend it faster."
    violations = NumberProvenanceGuard(sheet).check(response)
    assert violations == []


def test_small_ordinals_are_always_allowed() -> None:
    sheet = _sheet()
    response = _valid_response()
    response.closing = "This was your first of three focus areas -- prioritize it next game."
    violations = NumberProvenanceGuard(sheet).check(response)
    assert violations == []


def test_timestamp_components_from_findings_are_allowed() -> None:
    sheet = _sheet()
    response = _valid_response()
    response.narrations[0].explanation = "This started at 12 and ran until 16."
    violations = NumberProvenanceGuard(sheet).check(response)
    assert violations == []
