from lolcoach.detectors.base import DetectorOutcome, Severity
from lolcoach.detectors.ward_drought import WardDroughtDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 30


def _ctx(ward_times_s: list[float], *, team_position: str = "MIDDLE"):
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby(team_position=team_position).build()
    timeline = TimelineBuilder().frames(_DURATION_MIN)
    for t in ward_times_s:
        timeline = timeline.ward_placed(t_s=t, creator=1)
    return make_context(match, timeline.build())


def test_fewer_than_2_wards_is_insufficient_data() -> None:
    ctx = _ctx([500])
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.INSUFFICIENT_DATA
    assert "2 wards" in result.reason


def test_zero_wards_is_insufficient_data() -> None:
    ctx = _ctx([])
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.INSUFFICIENT_DATA


def test_gap_at_threshold_boundary_is_clean_for_non_support() -> None:
    # Gap must start at/after 8:00 (480s). 240s threshold -- exactly 240s gap is clean (not > threshold).
    ctx = _ctx([500, 740], team_position="MIDDLE")
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_gap_just_over_threshold_is_a_finding_for_non_support() -> None:
    ctx = _ctx([500, 741], team_position="MIDDLE")
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    gap = next(e for e in result.findings[0].evidence if e.key == "max_ward_gap_s")
    assert gap.value == 241.0


def test_support_uses_tighter_150s_threshold() -> None:
    # 200s gap is clean for MIDDLE (under 240) but a finding for UTILITY (over 150).
    ctx_mid = _ctx([500, 700], team_position="MIDDLE")
    assert WardDroughtDetector.run(ctx_mid).outcome == DetectorOutcome.CLEAN

    ctx_support = _ctx([500, 700], team_position="UTILITY")
    result = WardDroughtDetector.run(ctx_support)
    assert result.outcome == DetectorOutcome.FINDINGS


def test_gaps_before_8_minutes_are_not_counted() -> None:
    # A huge gap that starts before 8:00 should never trigger, no matter how long.
    ctx = _ctx([10, 470], team_position="MIDDLE")
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_unknown_team_position_defaults_to_non_support_threshold() -> None:
    ctx = _ctx([500, 700], team_position="")
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN  # 200s < 240s default threshold


def test_severity_scales_with_gap_ratio() -> None:
    # 1.5x the threshold (240 * 1.5 = 360s) -- at the major boundary.
    ctx = _ctx([500, 500 + 360], team_position="MIDDLE")
    result = WardDroughtDetector.run(ctx)
    assert result.findings[0].severity == Severity.MAJOR


def test_finding_timestamps_bound_the_gap() -> None:
    ctx = _ctx([500, 800], team_position="MIDDLE")
    result = WardDroughtDetector.run(ctx)
    assert result.findings[0].timestamps_s == (500.0, 800.0)


def test_only_subjects_own_wards_count() -> None:
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby(team_position="MIDDLE").build()
    timeline = (
        TimelineBuilder()
        .frames(_DURATION_MIN)
        .ward_placed(t_s=500, creator=1)
        .ward_placed(t_s=550, creator=6)  # someone else's ward -- should not fill the subject's gap
        .ward_placed(t_s=900, creator=1)
        .build()
    )
    ctx = make_context(match, timeline)
    result = WardDroughtDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    gap = next(e for e in result.findings[0].evidence if e.key == "max_ward_gap_s")
    assert gap.value == 400.0
