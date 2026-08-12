from lolcoach.detectors.base import DetectorOutcome, Severity
from lolcoach.detectors.time_dead import TimeDeadDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 30  # 1800s -- 12% = 216s, 18% = 324s


def _ctx(subject_dead_s: float, *, kills: list[dict] | None = None):
    match = (
        MatchBuilder()
        .duration_minutes(_DURATION_MIN)
        .with_full_lobby(total_time_spent_dead=subject_dead_s)
        .build()
    )
    builder = TimelineBuilder().frames(_DURATION_MIN)
    if kills:
        for k in kills:
            builder = builder.kill(**k)
    timeline = builder.build()
    return make_context(match, timeline)


def test_below_concerning_threshold_is_clean() -> None:
    ctx = _ctx(subject_dead_s=200)  # 11.1%
    result = TimeDeadDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_between_concerning_and_severe_is_moderate() -> None:
    ctx = _ctx(subject_dead_s=250)  # 13.9%
    result = TimeDeadDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert result.findings[0].severity == Severity.MODERATE


def test_above_severe_threshold_is_major() -> None:
    ctx = _ctx(subject_dead_s=400)  # 22.2%
    result = TimeDeadDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert result.findings[0].severity == Severity.MAJOR


def test_finding_reports_death_count_from_timeline() -> None:
    ctx = _ctx(
        subject_dead_s=400,
        kills=[
            {"t_s": 300, "killer": 6, "victim": 1},
            {"t_s": 1500, "killer": 7, "victim": 1},
        ],
    )
    result = TimeDeadDetector.run(ctx)
    death_count = next(e for e in result.findings[0].evidence if e.key == "death_count")
    assert death_count.value == 2


def test_late_game_deaths_dominate_cost_share() -> None:
    # A death at level ~16, 28 minutes in costs far more than one at level
    # ~4, 4 minutes in -- late_game_death_cost_share should reflect that.
    ctx = _ctx(
        subject_dead_s=400,
        kills=[
            {"t_s": 4 * 60, "killer": 6, "victim": 1},
            {"t_s": 28 * 60, "killer": 6, "victim": 1},
        ],
    )
    result = TimeDeadDetector.run(ctx)
    late_share = next(e for e in result.findings[0].evidence if e.key == "late_game_death_cost_share")
    assert late_share.value > 60.0  # majority of cost from the late death


def test_clean_result_reports_role_cohort_peer_comparison() -> None:
    match = (
        MatchBuilder()
        .duration_minutes(_DURATION_MIN)
        .with_full_lobby(total_time_spent_dead=100)
        .build()
    )
    match.raw["info"]["participants"][5]["totalTimeSpentDead"] = 50  # role cohort peer (pid 6, TOP team200)
    timeline = TimelineBuilder().frames(_DURATION_MIN).build()
    ctx = make_context(match, timeline)
    result = TimeDeadDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN
    share_evidence = result.headline_metrics[0]
    assert share_evidence.peer_value is not None
