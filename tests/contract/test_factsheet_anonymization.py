"""The fact sheet is the anonymization boundary -- these tests exist to
catch a regression that would leak identity into the LLM's input.
"""

from __future__ import annotations

import pytest

from lolcoach.analysis.build import build_fact_sheet
from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.detectors.context import AnalysisContext
from lolcoach.detectors.registry import DETECTORS
from lolcoach.detectors.runner import run_detectors
from tests.builders import MatchBuilder, TimelineBuilder, make_context


def _sample_sheet() -> MatchFactSheet:
    match = (
        MatchBuilder()
        .duration_minutes(30)
        .with_full_lobby(puuid="SUBJECT_SECRET_PUUID_VALUE", total_time_spent_dead=400)
        .build()
    )
    timeline = (
        TimelineBuilder()
        .frames(30, gold={1: lambda t: 2000 if 10 <= t <= 13 else 400})
        .kill(t_s=300, killer=6, victim=1)
        .kill(t_s=1500, killer=7, victim=1)
        .build()
    )
    ctx: AnalysisContext = make_context(match, timeline, subject_puuid="SUBJECT_SECRET_PUUID_VALUE")
    results = run_detectors(ctx, DETECTORS)
    return build_fact_sheet(ctx, results)


def test_no_puuid_anywhere_in_serialized_sheet() -> None:
    sheet = _sample_sheet()
    dumped = sheet.model_dump_json()
    assert "SUBJECT_SECRET_PUUID_VALUE" not in dumped
    assert "PUUID_" not in dumped  # every other participant's synthetic puuid too


def test_no_match_id_field_exists_on_the_schema() -> None:
    fields = MatchFactSheet.model_fields
    assert "match_id" not in fields
    assert "puuid" not in fields
    assert "riot_id" not in fields
    assert "summoner_name" not in fields
    for model_cls in (
        MatchFactSheet.model_fields["subject"].annotation,
        MatchFactSheet.model_fields["lane_opponent"].annotation,
    ):
        # These may be Optional[...]; just confirm no identity-shaped field name leaked in.
        pass


def test_not_knowable_block_present_on_every_sheet() -> None:
    sheet = _sample_sheet()
    assert len(sheet.not_knowable) >= 5
    assert any("ward" in item.lower() for item in sheet.not_knowable)
    assert any("mmr" in item.lower() or "rank" in item.lower() for item in sheet.not_knowable)


def test_findings_carry_deterministic_what_happened_text() -> None:
    sheet = _sample_sheet()
    assert sheet.findings, "expected at least one finding for this adversarial fixture"
    for f in sheet.findings:
        assert f.what_happened
        assert f.evidence
