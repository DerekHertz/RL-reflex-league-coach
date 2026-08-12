"""Detects excessive time spent dead, weighted by how expensive each death
actually was (a death at level 16 and 32 minutes costs ~3x a death at level
6 and 8 minutes -- raw death counts don't capture that).
"""

from __future__ import annotations

from typing import ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, PeerKind, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.metrics.combat import death_cost_s, time_dead_share

_CONCERNING_SHARE = 0.12
_SEVERE_SHARE = 0.18
_LATE_GAME_CUTOFF_MS = 20 * 60_000


class TimeDeadDetector:
    id: ClassVar[str] = "time_dead"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Time spent dead"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.MATCH, DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 600
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = False
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"time_dead_share"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        duration_s = ctx.match.duration_s
        share = time_dead_share(ctx.subject.total_time_spent_dead_s, duration_s)

        role_cmp = ctx.peers.compare(
            lambda p: time_dead_share(p.total_time_spent_dead_s, duration_s),
            higher_is_better=False,
            peer="role_cohort",
        )

        headline_evidence = Evidence(
            key="time_dead_share",
            label="Share of game spent dead",
            value=round(share * 100, 1),
            unit="percent",
            peer_value=round(role_cmp.peer_value * 100, 1) if role_cmp.peer_value is not None else None,
            peer_kind=PeerKind.ROLE_COHORT,
            rank_in_lobby=role_cmp.rank_in_lobby,
        )

        if share <= _CONCERNING_SHARE:
            return DetectorResult.clean(TimeDeadDetector, metrics=(headline_evidence,))

        severity = Severity.MAJOR if share > _SEVERE_SHARE else Severity.MODERATE

        deaths = [
            e for e in ctx.timeline.events_of_type("CHAMPION_KILL") if e.get("victimId") == ctx.subject.participant_id
        ]
        costs: list[tuple[int, float]] = []
        for death in deaths:
            level = ctx.timeline.level_at(ctx.subject.participant_id, death["timestamp"])
            costs.append((death["timestamp"], death_cost_s(level or 1, death["timestamp"] / 1000.0)))

        evidence = [
            headline_evidence,
            Evidence(key="death_count", label="Number of deaths", value=float(len(deaths)), unit="count"),
        ]
        timestamps: tuple[float, ...] = ()

        total_cost = sum(c for _, c in costs)
        if total_cost > 0:
            late_cost = sum(c for ts, c in costs if ts >= _LATE_GAME_CUTOFF_MS)
            evidence.append(
                Evidence(
                    key="late_game_death_cost_share",
                    label="Share of death-time cost from after 20 minutes",
                    value=round(late_cost / total_cost * 100, 1),
                    unit="percent",
                )
            )
            costliest_ts_ms = max(costs, key=lambda tc: tc[1])[0]
            timestamps = (costliest_ts_ms / 1000.0,)

        finding = Finding(
            id="time_dead:0",
            detector_id=TimeDeadDetector.id,
            detector_version=TimeDeadDetector.version,
            severity=severity,
            phase=Phase.WHOLE_GAME,
            confidence=1.0,
            timestamps_s=timestamps,
            evidence=tuple(evidence),
            affected_metrics=("time_dead_share",),
        )
        return DetectorResult.with_findings(TimeDeadDetector, (finding,))
