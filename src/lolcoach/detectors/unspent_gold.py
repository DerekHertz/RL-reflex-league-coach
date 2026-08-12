"""Detects runs of holding a large amount of unspent gold.

Highest signal-to-effort detector in the v1 set: needs only participant
frames, is completely unambiguous (either you were sitting on gold or you
weren't), and narrates cleanly ("you had 2800g unspent for 4 minutes").
"""

from __future__ import annotations

from typing import ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.metrics.economy import unspent_gold_series

_THRESHOLD_GOLD = 1400
_MIN_RUN_FRAMES = 3


class UnspentGoldDetector:
    id: ClassVar[str] = "unspent_gold"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Sitting on gold"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 600
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = False
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"unspent_gold_minutes", "peak_unspent_gold"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        series = unspent_gold_series(ctx.timeline, ctx.subject.participant_id)
        frame_interval_min = ctx.timeline.frame_interval_ms / 60_000.0

        runs = _find_runs(series, threshold=_THRESHOLD_GOLD, min_len=_MIN_RUN_FRAMES)
        wasted_minutes = sum(1 for _, gold in series if gold > _THRESHOLD_GOLD) * frame_interval_min
        peak_gold = max((gold for _, gold in series), default=0)

        headline = (
            Evidence(
                key="unspent_gold_minutes",
                label="Minutes spent over 1400 unspent gold",
                value=round(wasted_minutes, 1),
                unit="count",
            ),
            Evidence(key="peak_unspent_gold", label="Peak unspent gold", value=float(peak_gold), unit="gold"),
        )

        if not runs:
            return DetectorResult.clean(UnspentGoldDetector, metrics=headline)

        findings = []
        for i, run in enumerate(runs):
            start_ts, end_ts = run[0][0], run[-1][0]
            peak = max(gold for _, gold in run)
            severity = Severity.MAJOR if peak > 3000 else Severity.MODERATE if peak > 2000 else Severity.MINOR
            findings.append(
                Finding(
                    id=f"unspent_gold:{i}",
                    detector_id=UnspentGoldDetector.id,
                    detector_version=UnspentGoldDetector.version,
                    severity=severity,
                    phase=_phase_for(start_ts),
                    confidence=1.0,
                    timestamps_s=(start_ts / 1000.0, end_ts / 1000.0),
                    evidence=(
                        Evidence(key="peak_gold", label="Peak gold held", value=float(peak), unit="gold"),
                        Evidence(
                            key="run_duration_min",
                            label="Minutes held above threshold",
                            value=round((end_ts - start_ts) / 60_000.0 + frame_interval_min, 1),
                            unit="count",
                        ),
                    ),
                    affected_metrics=("unspent_gold_minutes",),
                )
            )
        return DetectorResult.with_findings(UnspentGoldDetector, tuple(findings))


def _find_runs(
    series: list[tuple[int, int]], *, threshold: int, min_len: int
) -> list[list[tuple[int, int]]]:
    runs: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for ts, gold in series:
        if gold > threshold:
            current.append((ts, gold))
        else:
            if len(current) >= min_len:
                runs.append(current)
            current = []
    if len(current) >= min_len:
        runs.append(current)
    return runs


def _phase_for(ts_ms: float) -> Phase:
    minute = ts_ms / 60_000.0
    if minute < 14:
        return Phase.EARLY
    if minute < 25:
        return Phase.MID
    return Phase.LATE
