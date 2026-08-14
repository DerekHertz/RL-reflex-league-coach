from lolcoach.detectors.base import DetectorOutcome, Severity
from lolcoach.detectors.death_regions import DeathRegionsDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context

_DURATION_MIN = 30

# Hand-picked raw (blue-side) coordinates for distinct, non-overlapping
# regions -- see tests/unit/test_geometry.py for how these were derived.
_OWN_BOT_JUNGLE = (6251, 2145)  # depth ~0.29 -- not "deep"
_OWN_TOP_JUNGLE = (2128, 7808)  # depth ~0.34
_MID_LANE = (7375, 7883)  # depth ~0.52
_BOT_LANE = (12247, 4712)  # depth ~0.57
_TOP_LANE = (2503, 14829)  # depth ~0.58
_ENEMY_TOP_JUNGLE = (8499, 12262)  # depth ~0.70 -- "deep"
_ENEMY_BOT_JUNGLE = (12622, 6826)  # depth ~0.66 -- "deep"
_ENEMY_FOUNTAIN = (14195, 13848)  # depth ~0.94 -- "deep", distinct region from the other two
_DRAGON_PIT = (9899, 4470)  # depth ~0.49 -- landmark, not deep


def _ctx(kills: list[dict]):
    match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby().build()
    timeline = TimelineBuilder().frames(_DURATION_MIN)
    for k in kills:
        timeline = timeline.kill(**k)
    return make_context(match, timeline.build())


def _death(t_s: float, pos: tuple[int, int]) -> dict:
    return {"t_s": t_s, "killer": 6, "victim": 1, "pos": pos}


def test_fewer_than_3_deaths_with_position_is_not_applicable() -> None:
    ctx = _ctx([_death(300, _MID_LANE), _death(600, _BOT_LANE)])
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.NOT_APPLICABLE
    assert "3 deaths" in result.reason


def test_deaths_without_recorded_position_do_not_count() -> None:
    # 3 kills but only 2 carry a position -> still below the minimum.
    ctx = _ctx(
        [
            {"t_s": 300, "killer": 6, "victim": 1},  # no pos
            _death(600, _BOT_LANE),
            _death(900, _MID_LANE),
        ]
    )
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.NOT_APPLICABLE


def test_region_concentration_just_under_40_percent_is_clean() -> None:
    # 10 deaths, top region has 3 (30%) -- below the 40% threshold.
    kills = (
        [_death(100 + 10 * i, _OWN_BOT_JUNGLE) for i in range(3)]
        + [_death(200 + 10 * i, _OWN_TOP_JUNGLE) for i in range(2)]
        + [_death(300 + 10 * i, _MID_LANE) for i in range(2)]
        + [_death(400 + 10 * i, _BOT_LANE) for i in range(2)]
        + [_death(500, _TOP_LANE)]
    )
    ctx = _ctx(kills)
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_region_concentration_at_40_percent_boundary_is_moderate_finding() -> None:
    # 10 deaths, top region has exactly 4 (40%) -- at the threshold, inclusive.
    kills = (
        [_death(100 + 10 * i, _OWN_BOT_JUNGLE) for i in range(4)]
        + [_death(200 + 10 * i, _OWN_TOP_JUNGLE) for i in range(2)]
        + [_death(300 + 10 * i, _MID_LANE) for i in range(2)]
        + [_death(400 + 10 * i, _BOT_LANE) for i in range(2)]
    )
    ctx = _ctx(kills)
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    finding = result.findings[0]
    assert finding.severity == Severity.MODERATE
    concentration = next(e for e in finding.evidence if e.key == "death_region_concentration")
    assert concentration.value == 40.0
    assert len(finding.positions) == 4


def test_region_concentration_at_60_percent_boundary_is_major() -> None:
    # 10 deaths, top region has exactly 6 (60%) -- at the "major" threshold.
    kills = [_death(100 + 10 * i, _OWN_BOT_JUNGLE) for i in range(6)] + [
        _death(200 + 10 * i, _MID_LANE) for i in range(4)
    ]
    ctx = _ctx(kills)
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert result.findings[0].severity == Severity.MAJOR


def test_deep_deaths_with_no_nearby_objective_flagged_separately() -> None:
    # 5 deaths: 3 scattered across distinct "deep" regions (60% deep, but no
    # single region concentrated >=40%), 2 shallow.
    kills = [
        _death(100, _ENEMY_TOP_JUNGLE),
        _death(200, _ENEMY_BOT_JUNGLE),
        _death(300, _ENEMY_FOUNTAIN),
        _death(400, _OWN_BOT_JUNGLE),
        _death(500, _MID_LANE),
    ]
    ctx = _ctx(kills)
    result = DeathRegionsDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "death_regions:deep"
    assert finding.severity == Severity.MAJOR
    deep_count = next(e for e in finding.evidence if e.key == "deep_death_count")
    assert deep_count.value == 3
    assert len(finding.positions) == 3


def test_deep_death_excluded_when_objective_taken_nearby() -> None:
    # Same deep positions, but each death has a same-team objective takedown
    # within 60s -- none of these should count as "deep for no reason".
    kills = [
        _death(100, _ENEMY_TOP_JUNGLE),
        _death(200, _ENEMY_BOT_JUNGLE),
        _death(300, _DRAGON_PIT),
    ]
    ctx_builder_match = MatchBuilder().duration_minutes(_DURATION_MIN).with_full_lobby().build()
    timeline = TimelineBuilder().frames(_DURATION_MIN)
    for k in kills:
        timeline = timeline.kill(**k)
    timeline = (
        timeline.elite_monster(t_s=110, team=100, monster="DRAGON")
        .elite_monster(t_s=210, team=100, monster="DRAGON")
        .elite_monster(t_s=310, team=100, monster="DRAGON")
    )
    ctx = make_context(ctx_builder_match, timeline.build())
    result = DeathRegionsDetector.run(ctx)
    # Only 3 deaths total -- meets the minimum but none are "deep for no
    # reason" once objectives are accounted for, and none concentrate in one
    # region (all 3 in distinct regions) -- so this is clean.
    assert result.outcome == DetectorOutcome.CLEAN
    deep_share = next(e for e in result.headline_metrics if e.key == "deep_death_share")
    assert deep_share.value == 0.0
