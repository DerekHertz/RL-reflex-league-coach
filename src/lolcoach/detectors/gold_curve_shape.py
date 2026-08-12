"""Detects the "won lane, lost the game" pattern: a solid gold lead at 15
minutes that evaporates by 25. This is a genuinely different coaching
message from "you can't last-hit" -- the laning was fine, the mid-game
wasn't.
"""

from __future__ import annotations

from typing import ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, PeerKind, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.metrics.economy import gold_diff_at

_LEAD_THRESHOLD_GOLD = 800
_COLLAPSE_THRESHOLD_GOLD = 1500


class GoldCurveShapeDetector:
    id: ClassVar[str] = "gold_curve_shape"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Gold lead trajectory"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 900
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = False
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"gold_diff_at_15", "gold_diff_at_25"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        opponent = ctx.peers.lane_opponent
        if opponent is None:
            return DetectorResult.na(GoldCurveShapeDetector, "no lane opponent: teamPosition unavailable")

        duration_min = ctx.match.duration_s / 60.0
        subject_id, opponent_id = ctx.subject.participant_id, opponent.participant_id

        gd15 = gold_diff_at(ctx.timeline, subject_id, opponent_id, 15) if duration_min >= 15 else None
        gd25 = gold_diff_at(ctx.timeline, subject_id, opponent_id, 25) if duration_min >= 25 else None

        headline = tuple(
            Evidence(
                key=f"gold_diff_at_{minute}",
                label=f"Gold diff vs lane opponent @{minute}min",
                value=float(value),
                unit="gold",
                peer_kind=PeerKind.LANE_OPPONENT,
            )
            for minute, value in ((15, gd15), (25, gd25))
            if value is not None
        )

        collapsed = gd15 is not None and gd25 is not None and gd15 > _LEAD_THRESHOLD_GOLD and gd25 < gd15 - _COLLAPSE_THRESHOLD_GOLD
        if not collapsed:
            return DetectorResult.clean(GoldCurveShapeDetector, metrics=headline)

        assert gd15 is not None and gd25 is not None
        finding = Finding(
            id="gold_curve_shape:0",
            detector_id=GoldCurveShapeDetector.id,
            detector_version=GoldCurveShapeDetector.version,
            severity=Severity.MODERATE,
            phase=Phase.MID,
            confidence=1.0,
            timestamps_s=(15 * 60.0, 25 * 60.0),
            evidence=(
                Evidence(key="gold_diff_at_15", label="Gold lead @15min", value=float(gd15), unit="gold", peer_kind=PeerKind.LANE_OPPONENT),
                Evidence(key="gold_diff_at_25", label="Gold lead @25min", value=float(gd25), unit="gold", peer_kind=PeerKind.LANE_OPPONENT),
                Evidence(key="lead_lost", label="Gold lead lost between 15 and 25 min", value=float(gd15 - gd25), unit="gold"),
            ),
            affected_metrics=("gold_diff_at_15", "gold_diff_at_25"),
        )
        return DetectorResult.with_findings(GoldCurveShapeDetector, (finding,))
