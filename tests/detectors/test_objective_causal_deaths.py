from lolcoach.detectors.base import DetectorOutcome, Severity
from lolcoach.detectors.objective_causal_deaths import ObjectiveCausalDeathsDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 30


def _ctx(*, level: int, kills: list[dict], monsters: list[dict]):
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby().build()
    builder = TimelineBuilder().frames(_DURATION_MIN, level={1: level})
    for k in kills:
        builder = builder.kill(**k)
    for m in monsters:
        builder = builder.elite_monster(**m)
    return make_context(match, builder.build())


def test_still_dead_when_objective_falls_is_flagged() -> None:
    # level 6 -> 16s respawn. Died 10s before the objective -> still has 6s
    # left on the timer when it falls.
    ctx = _ctx(
        level=6,
        kills=[{"t_s": 500, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 510, "team": 200, "monster": "DRAGON"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    finding = result.findings[0]
    assert finding.severity == Severity.MODERATE
    margin = next(e for e in finding.evidence if e.key == "still_dead_margin_s")
    assert margin.value == 6.0
    time_since = next(e for e in finding.evidence if e.key == "time_since_death_s")
    assert time_since.value == 10.0


def test_respawned_before_objective_falls_is_not_flagged() -> None:
    # Same 16s respawn, but the objective falls 20s after death -- subject
    # was back up 4s before it happened.
    ctx = _ctx(
        level=6,
        kills=[{"t_s": 500, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 520, "team": 200, "monster": "DRAGON"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_death_outside_45s_preceding_window_is_not_flagged() -> None:
    ctx = _ctx(
        level=6,
        kills=[{"t_s": 400, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 500, "team": 200, "monster": "DRAGON"}],  # 100s gap
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_gap_exactly_45s_with_long_respawn_is_flagged() -> None:
    # level 18 -> 52.5s respawn. Death at 100s, objective at exactly 145s
    # (45.000s later) -- at the inclusive boundary of the preceding window,
    # and still comfortably covered by the respawn timer.
    ctx = _ctx(
        level=18,
        kills=[{"t_s": 100, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 145, "team": 200, "monster": "DRAGON"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS


def test_gap_just_over_45s_is_not_flagged() -> None:
    ctx = _ctx(
        level=18,
        kills=[{"t_s": 100, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 145.001, "team": 200, "monster": "DRAGON"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_baron_is_major_severity() -> None:
    ctx = _ctx(
        level=6,
        kills=[{"t_s": 500, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 510, "team": 200, "monster": "BARON_NASHOR"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert result.findings[0].severity == Severity.MAJOR


def test_same_team_objective_is_never_flagged() -> None:
    # The subject's OWN team taking an objective is never a "gave up an
    # objective" finding, no matter the death timing.
    ctx = _ctx(
        level=6,
        kills=[{"t_s": 500, "killer": 6, "victim": 1}],
        monsters=[{"t_s": 510, "team": 100, "monster": "DRAGON"}],
    )
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_no_objectives_at_all_is_clean() -> None:
    ctx = _ctx(level=6, kills=[{"t_s": 500, "killer": 6, "victim": 1}], monsters=[])
    result = ObjectiveCausalDeathsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN
    count = next(e for e in result.headline_metrics if e.key == "objective_causal_death_count")
    assert count.value == 0.0
