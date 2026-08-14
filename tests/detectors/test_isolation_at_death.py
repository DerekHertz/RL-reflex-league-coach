from lolcoach.detectors.base import DetectorOutcome, Severity
from lolcoach.detectors.isolation_at_death import IsolationAtDeathDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 20

# enemy_bot_jungle for the blue-side subject -- depth ~0.655, comfortably
# past the 0.6 "deep" threshold. See tests/unit/test_geometry.py.
_SUBJECT_DEEP = (12622, 6826)
# own_bot_jungle -- depth ~0.29, comfortably NOT deep.
_SUBJECT_SHALLOW = (6251, 2145)

_ALLY_FAR = (100, 100)  # >4000 units from _SUBJECT_DEEP
_ALLY_CLOSE = (_SUBJECT_DEEP[0] + 500, _SUBJECT_DEEP[1])  # 500 units away
_ALLY_MODERATE = (_SUBJECT_DEEP[0] + 5000, _SUBJECT_DEEP[1])  # exactly 5000 units away


def _ctx(deaths_s: list[float], *, subject_pos, ally_pos):
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby().build()
    positions = {1: subject_pos, 2: ally_pos, 3: ally_pos, 4: ally_pos, 5: ally_pos}
    builder = TimelineBuilder().frames(_DURATION_MIN, position=positions)
    for t in deaths_s:
        builder = builder.kill(t_s=t, killer=6, victim=1)
    return make_context(match, builder.build())


def test_fewer_than_2_usable_deaths_is_not_applicable() -> None:
    ctx = _ctx([300], subject_pos=_SUBJECT_DEEP, ally_pos=_ALLY_FAR)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.NOT_APPLICABLE
    assert "2 deaths" in result.reason


def test_deaths_without_any_position_data_are_not_applicable() -> None:
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby().build()
    timeline = TimelineBuilder().frames(_DURATION_MIN).kill(t_s=300, killer=6, victim=1).kill(t_s=600, killer=6, victim=1).build()
    ctx = make_context(match, timeline)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.NOT_APPLICABLE


def test_far_from_allies_and_deep_is_flagged_major() -> None:
    ctx = _ctx([300, 600], subject_pos=_SUBJECT_DEEP, ally_pos=_ALLY_FAR)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert len(result.findings) == 2
    for finding in result.findings:
        assert finding.severity == Severity.MAJOR
        dist = next(e for e in finding.evidence if e.key == "nearest_ally_dist")
        assert dist.value > 6000


def test_moderate_distance_is_moderate_severity() -> None:
    ctx = _ctx([300, 600], subject_pos=_SUBJECT_DEEP, ally_pos=_ALLY_MODERATE)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert result.findings[0].severity == Severity.MODERATE
    dist = next(e for e in result.findings[0].evidence if e.key == "nearest_ally_dist")
    assert dist.value == 5000.0


def test_close_ally_is_clean_even_when_deep() -> None:
    ctx = _ctx([300, 600], subject_pos=_SUBJECT_DEEP, ally_pos=_ALLY_CLOSE)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN
    count = next(e for e in result.headline_metrics if e.key == "isolated_death_count")
    assert count.value == 0.0


def test_shallow_position_is_clean_even_when_far_from_allies() -> None:
    ctx = _ctx([300, 600], subject_pos=_SUBJECT_SHALLOW, ally_pos=_ALLY_FAR)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_finding_positions_carry_side_normalized_subject_position() -> None:
    ctx = _ctx([300, 600], subject_pos=_SUBJECT_DEEP, ally_pos=_ALLY_FAR)
    result = IsolationAtDeathDetector.run(ctx)
    assert result.findings[0].positions == ((float(_SUBJECT_DEEP[0]), float(_SUBJECT_DEEP[1])),)
