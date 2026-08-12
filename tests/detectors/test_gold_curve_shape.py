from lolcoach.detectors.base import DetectorOutcome
from lolcoach.detectors.gold_curve_shape import GoldCurveShapeDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 30


def _ctx(subject_gold, opponent_gold, *, subject_team_position: str | None = None):
    overrides = {"team_position": subject_team_position} if subject_team_position is not None else {}
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby(**overrides).build()
    timeline = TimelineBuilder().frames(_DURATION_MIN, gold={1: subject_gold, 6: opponent_gold}).build()
    return make_context(match, timeline)


def test_won_lane_lost_game_pattern_is_flagged() -> None:
    # Subject builds a >800g lead by 15min that fully evaporates by 25min.
    subject = lambda t: 500 + t * 400 if t <= 15 else 6500 + (t - 15) * 100
    opponent = lambda t: 500 + t * 300
    ctx = _ctx(subject, opponent)
    result = GoldCurveShapeDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    gd15 = next(e for e in result.findings[0].evidence if e.key == "gold_diff_at_15")
    gd25 = next(e for e in result.findings[0].evidence if e.key == "gold_diff_at_25")
    assert gd15.value > 800
    assert gd25.value < gd15.value - 1500


def test_small_stable_lead_is_clean() -> None:
    subject = lambda t: 500 + t * 400
    opponent = lambda t: 500 + t * 380  # never diverges past the 800g lead threshold
    ctx = _ctx(subject, opponent)
    result = GoldCurveShapeDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_lead_that_holds_is_clean() -> None:
    # Big early lead that GROWS (not collapses) by 25 min should not fire.
    subject = lambda t: 500 + t * 500
    opponent = lambda t: 500 + t * 200
    ctx = _ctx(subject, opponent)
    result = GoldCurveShapeDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_no_lane_opponent_is_not_applicable() -> None:
    ctx = _ctx(lambda t: 1000, lambda t: 1000, subject_team_position="")
    result = GoldCurveShapeDetector.run(ctx)
    assert result.outcome == DetectorOutcome.NOT_APPLICABLE
    assert "lane opponent" in result.reason


def test_short_game_below_15_min_is_not_applicable_via_runner() -> None:
    from lolcoach.detectors.runner import run_detectors

    match = MatchBuilder().duration_minutes(10).with_full_lobby().build()
    timeline = TimelineBuilder().frames(10, gold={1: lambda t: 1000, 6: lambda t: 1000}).build()
    ctx = make_context(match, timeline)
    results = run_detectors(ctx, [GoldCurveShapeDetector])
    assert results[0].outcome == DetectorOutcome.NOT_APPLICABLE
