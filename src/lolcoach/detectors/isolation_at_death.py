"""Detects deaths that happened deep in enemy territory, far from the
nearest ally -- the "caught out alone" pattern, as opposed to a death inside
a full 5v5 fight.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.domain.geometry import map_depth, side_normalize, to_unit_square
from lolcoach.domain.timeline import Frame

_MIN_USABLE_DEATHS = 2
_ISOLATION_DIST = 4000.0
_ISOLATION_DIST_MAJOR = 6000.0
_DEEP_DEPTH_THRESHOLD = 0.6


class IsolationAtDeathDetector:
    id: ClassVar[str] = "isolation_at_death"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Caught out alone"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 600
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = True
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"isolated_death_count"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        deaths = [e for e in ctx.timeline.events_of_type("CHAMPION_KILL") if e.get("victimId") == ctx.subject.participant_id]

        usable: list[tuple[dict[str, Any], float, float, tuple[float, float]]] = []  # (death_event, min_ally_dist, depth, subject_pos)
        for death in deaths:
            frame = ctx.timeline.frame_at_or_before(death["timestamp"] - 1)
            if frame is None:
                continue
            result = _isolation_at(frame, ctx.subject.participant_id, ctx.subject.team_id, ctx.match.participants)
            if result is None:
                continue
            min_dist, depth, subject_pos = result
            usable.append((death, min_dist, depth, subject_pos))

        if len(usable) < _MIN_USABLE_DEATHS:
            return DetectorResult.na(
                IsolationAtDeathDetector,
                f"fewer than {_MIN_USABLE_DEATHS} deaths with a usable preceding frame ({len(usable)} found)",
            )

        isolated = [
            (death, dist, depth, pos) for death, dist, depth, pos in usable if dist > _ISOLATION_DIST and depth > _DEEP_DEPTH_THRESHOLD
        ]

        headline = (Evidence(key="isolated_death_count", label="Deaths caught out alone deep in enemy territory", value=float(len(isolated)), unit="count"),)

        if not isolated:
            return DetectorResult.clean(IsolationAtDeathDetector, metrics=headline)

        findings = []
        for i, (death, dist, depth, subject_pos) in enumerate(isolated):
            severity = Severity.MAJOR if dist > _ISOLATION_DIST_MAJOR else Severity.MODERATE
            nx, ny = side_normalize(subject_pos[0], subject_pos[1], ctx.subject.team_id)
            findings.append(
                Finding(
                    id=f"isolation_at_death:{i}",
                    detector_id=IsolationAtDeathDetector.id,
                    detector_version=IsolationAtDeathDetector.version,
                    severity=severity,
                    phase=_phase_for(death["timestamp"]),
                    confidence=1.0,
                    timestamps_s=(death["timestamp"] / 1000.0,),
                    evidence=(
                        Evidence(key="nearest_ally_dist", label="Distance to nearest ally", value=round(dist, 0), unit="meters"),
                        Evidence(key="map_depth", label="Depth into enemy territory (0=own fountain, 1=enemy fountain)", value=round(depth, 2), unit="ratio"),
                    ),
                    affected_metrics=("isolated_death_count",),
                    positions=((nx, ny),),
                )
            )
        return DetectorResult.with_findings(IsolationAtDeathDetector, tuple(findings))


def _isolation_at(
    frame: Frame, subject_id: int, subject_team_id: int, all_participants: Any
) -> tuple[float, float, tuple[float, float]] | None:
    """Returns (min_ally_dist, depth, subject_raw_pos) at this frame, or None
    if the subject or all allies lack a position sample.

    "Living ally" is approximated here as "any teammate with a position in
    this frame" -- participantFrames always carries an entry for every
    participant regardless of whether they're alive at that instant, and
    working out true alive/dead state per frame from events is more
    involved than v1 needs. This can occasionally undercount isolation (a
    dead ally's last known position still counts as "nearby").
    """
    subject_frame = frame.participant_frame(subject_id)
    subject_pos = subject_frame.position
    if subject_pos is None:
        return None

    ally_ids = [p.participant_id for p in all_participants if p.team_id == subject_team_id and p.participant_id != subject_id]
    ally_positions = []
    for pid in ally_ids:
        pos = frame.participant_frame(pid).position
        if pos is not None:
            ally_positions.append(pos)
    if not ally_positions:
        return None

    min_dist = min(math.hypot(subject_pos[0] - ax, subject_pos[1] - ay) for ax, ay in ally_positions)

    nx, ny = side_normalize(subject_pos[0], subject_pos[1], subject_team_id)
    u, v = to_unit_square(nx, ny)
    depth = map_depth(u, v)
    return min_dist, depth, subject_pos


def _phase_for(ts_ms: float) -> Phase:
    minute = ts_ms / 60_000.0
    if minute < 14:
        return Phase.EARLY
    if minute < 25:
        return Phase.MID
    return Phase.LATE
