from lolcoach.detectors.base import DetectorOutcome
from lolcoach.detectors.unspent_gold import UnspentGoldDetector
from tests.builders import MatchBuilder, TimelineBuilder, make_context


def _ctx(gold_fn):
    match = MatchBuilder().duration_minutes(20).with_full_lobby().build()
    timeline = TimelineBuilder().frames(20, gold={1: gold_fn}).build()
    return make_context(match, timeline)


def test_gold_at_threshold_boundary_is_clean() -> None:
    # 1399 never exceeds the >1400 threshold -> CLEAN, even held the whole game.
    ctx = _ctx(lambda t: 1399)
    result = UnspentGoldDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_gold_just_over_threshold_for_3_frames_is_a_finding() -> None:
    ctx = _ctx(lambda t: 1401 if 5 <= t <= 7 else 400)
    result = UnspentGoldDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert len(result.findings) == 1
    peak = next(e for e in result.findings[0].evidence if e.key == "peak_gold")
    assert peak.value == 1401


def test_gold_over_threshold_for_only_2_frames_is_clean() -> None:
    # min run length is 3 frames -- a 2-frame spike doesn't count.
    ctx = _ctx(lambda t: 1500 if 5 <= t <= 6 else 400)
    result = UnspentGoldDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN


def test_two_separate_runs_produce_two_findings() -> None:
    ctx = _ctx(lambda t: 2000 if (3 <= t <= 5 or 15 <= t <= 18) else 400)
    result = UnspentGoldDetector.run(ctx)
    assert result.outcome == DetectorOutcome.FINDINGS
    assert len(result.findings) == 2


def test_high_peak_gold_is_major_severity() -> None:
    from lolcoach.detectors.base import Severity

    ctx = _ctx(lambda t: 3500 if 5 <= t <= 8 else 400)
    result = UnspentGoldDetector.run(ctx)
    assert result.findings[0].severity == Severity.MAJOR


def test_clean_result_still_carries_headline_metrics() -> None:
    ctx = _ctx(lambda t: 400)
    result = UnspentGoldDetector.run(ctx)
    assert result.outcome == DetectorOutcome.CLEAN
    keys = {e.key for e in result.headline_metrics}
    assert keys == {"unspent_gold_minutes", "peak_unspent_gold"}


def test_short_remake_is_not_applicable() -> None:
    from lolcoach.detectors.runner import run_detectors

    match = MatchBuilder().duration_minutes(4).with_full_lobby().build()
    timeline = TimelineBuilder().frames(4, gold={1: lambda t: 5000}).build()
    ctx = make_context(match, timeline)
    results = run_detectors(ctx, [UnspentGoldDetector])
    assert results[0].outcome == DetectorOutcome.NOT_APPLICABLE
    assert "minimum" in results[0].reason
