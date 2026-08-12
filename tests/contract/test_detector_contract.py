"""Invariants ALL detectors must satisfy, checked against synthetic contexts
covering the range of shapes a real detector will see: a normal game, a
remake-length game, and a game with no lane opponent (ARAM/Arena-shaped).
"""

from __future__ import annotations

import pytest

from lolcoach.detectors.base import DetectorOutcome
from lolcoach.detectors.registry import DETECTORS
from lolcoach.detectors.runner import run_detectors
from tests.builders import MatchBuilder, TimelineBuilder, make_context


def _normal_game_ctx():
    match = MatchBuilder().duration_minutes(30).with_full_lobby(total_time_spent_dead=300).build()
    timeline = (
        TimelineBuilder()
        .frames(30, gold={1: lambda t: 500 + t * 350, 6: lambda t: 500 + t * 300})
        .kill(t_s=400, killer=6, victim=1)
        .kill(t_s=1500, killer=7, victim=1)
        .ward_placed(t_s=200, creator=1)
        .build()
    )
    return make_context(match, timeline)


def _remake_ctx():
    match = MatchBuilder().duration_minutes(3).with_full_lobby().build()
    timeline = TimelineBuilder().frames(3).build()
    return make_context(match, timeline)


def _no_lane_opponent_ctx():
    match = MatchBuilder().duration_minutes(20).with_full_lobby(team_position="").build()
    timeline = TimelineBuilder().frames(20).build()
    return make_context(match, timeline)


CONTEXTS = {
    "normal_game": _normal_game_ctx,
    "remake": _remake_ctx,
    "no_lane_opponent": _no_lane_opponent_ctx,
}


@pytest.mark.parametrize("detector", DETECTORS, ids=lambda d: d.id)
@pytest.mark.parametrize("ctx_name", CONTEXTS, ids=lambda n: n)
def test_detector_contract(detector, ctx_name: str) -> None:
    ctx = CONTEXTS[ctx_name]()
    results = run_detectors(ctx, [detector])
    assert len(results) == 1
    result = results[0]

    # Never raises out of run_detectors -- ERROR is captured, not propagated.
    assert result.outcome != DetectorOutcome.ERROR, result.reason

    # Non-FINDINGS outcomes that require a reason must have a non-empty one.
    if result.outcome in (DetectorOutcome.NOT_APPLICABLE, DetectorOutcome.INSUFFICIENT_DATA):
        assert result.reason

    # FINDINGS outcomes carry at least one finding, each with evidence and
    # in-bounds timestamps.
    if result.outcome == DetectorOutcome.FINDINGS:
        assert result.findings
        for finding in result.findings:
            assert finding.evidence
            assert 0.0 <= finding.confidence <= 1.0
            for ts in finding.timestamps_s:
                assert 0.0 <= ts <= ctx.match.duration_s
            for metric_key in finding.affected_metrics:
                assert metric_key in detector.emits_metrics

    # Fast -- these are pure sync functions of small in-memory data.
    assert result.duration_ms < 500


def test_detector_ids_are_unique() -> None:
    ids = [d.id for d in DETECTORS]
    assert len(ids) == len(set(ids))


def test_detector_ids_are_stable_snake_case() -> None:
    import re

    for d in DETECTORS:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", d.id), d.id
