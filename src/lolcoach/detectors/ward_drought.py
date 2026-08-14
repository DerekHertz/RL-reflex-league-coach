"""Detects long stretches with no warding by the subject.

`WARD_PLACED` events carry no position (a confirmed Riot API limitation --
see `factsheet.NOT_KNOWABLE`), so this can only ever measure vision *timing*:
the longest gap between two consecutive wards the subject placed. It can
never claim to know where a ward was or wasn't placed.
"""

from __future__ import annotations

from typing import ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.context import AnalysisContext

_EARLIEST_GAP_START_MS = 480_000  # 8:00 -- gaps that start before this aren't counted
_UTILITY_THRESHOLD_S = 150.0
_DEFAULT_THRESHOLD_S = 240.0
_MAJOR_RATIO = 1.5


class WardDroughtDetector:
    id: ClassVar[str] = "ward_drought"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Ward drought"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 900
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = False  # WARD_PLACED carries no position -- only timing is used here
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"max_ward_gap_s"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        ward_timestamps = sorted(
            e["timestamp"] for e in ctx.timeline.events_of_type("WARD_PLACED") if e.get("creatorId") == ctx.subject.participant_id
        )

        if len(ward_timestamps) < 2:
            return DetectorResult.insufficient(
                WardDroughtDetector, f"fewer than 2 wards placed by the subject ({len(ward_timestamps)} found)"
            )

        threshold_s = _UTILITY_THRESHOLD_S if ctx.subject.team_position == "UTILITY" else _DEFAULT_THRESHOLD_S

        gaps = [
            (ward_timestamps[i], ward_timestamps[i + 1])
            for i in range(len(ward_timestamps) - 1)
            if ward_timestamps[i] >= _EARLIEST_GAP_START_MS
        ]

        if not gaps:
            return DetectorResult.clean(
                WardDroughtDetector,
                metrics=(Evidence(key="max_ward_gap_s", label="Longest gap between wards (after 8:00)", value=0.0, unit="seconds"),),
            )

        start_ms, end_ms = max(gaps, key=lambda g: g[1] - g[0])
        max_gap_s = (end_ms - start_ms) / 1000.0

        headline = (Evidence(key="max_ward_gap_s", label="Longest gap between wards (after 8:00)", value=round(max_gap_s, 1), unit="seconds"),)

        if max_gap_s <= threshold_s:
            return DetectorResult.clean(WardDroughtDetector, metrics=headline)

        severity = Severity.MAJOR if max_gap_s >= threshold_s * _MAJOR_RATIO else Severity.MODERATE
        finding = Finding(
            id="ward_drought:0",
            detector_id=WardDroughtDetector.id,
            detector_version=WardDroughtDetector.version,
            severity=severity,
            phase=Phase.WHOLE_GAME,
            confidence=1.0,
            timestamps_s=(start_ms / 1000.0, end_ms / 1000.0),
            evidence=(
                Evidence(key="max_ward_gap_s", label="Longest gap between wards", value=round(max_gap_s, 1), unit="seconds"),
                Evidence(key="threshold_s", label="Gap threshold for this role", value=threshold_s, unit="seconds"),
                Evidence(key="wards_placed", label="Total wards placed", value=float(len(ward_timestamps)), unit="count"),
            ),
            affected_metrics=("max_ward_gap_s",),
        )
        return DetectorResult.with_findings(WardDroughtDetector, (finding,))
