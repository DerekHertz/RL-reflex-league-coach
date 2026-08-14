"""Detects deaths that directly enabled an enemy objective: the subject died
shortly before an enemy Dragon/Herald/Baron/Atakhan takedown, AND was still
on the respawn timer when the objective actually fell. Dying and respawning
in time to still contest (or at least not be the reason it was uncontested)
is explicitly NOT a finding -- only the conjunction of "died recently" AND
"still dead when it happened" counts.
"""

from __future__ import annotations

from typing import Any, ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.metrics.combat import death_cost_s

_PRECEDING_WINDOW_MS = 45_000
_MAJOR_MONSTER_TYPES = frozenset({"BARON_NASHOR"})


class ObjectiveCausalDeathsDetector:
    id: ClassVar[str] = "objective_causal_deaths"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Deaths that gave up objectives"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 900
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = True
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"objective_causal_death_count"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        subject_id = ctx.subject.participant_id

        enemy_objectives = [
            e for e in ctx.timeline.events_of_type("ELITE_MONSTER_KILL") if e.get("killerTeamId") != ctx.subject.team_id
        ]
        subject_deaths = [e for e in ctx.timeline.events_of_type("CHAMPION_KILL") if e.get("victimId") == subject_id]

        findings: list[Finding] = []
        for objective in enemy_objectives:
            match = _causal_death_for(objective, subject_deaths, ctx.timeline, subject_id)
            if match is None:
                continue
            death, cost_s, margin_s = match
            monster_type = objective.get("monsterType", "UNKNOWN")
            severity = Severity.MAJOR if monster_type in _MAJOR_MONSTER_TYPES else Severity.MODERATE
            findings.append(
                Finding(
                    id=f"objective_causal_deaths:{objective['timestamp']}",
                    detector_id=ObjectiveCausalDeathsDetector.id,
                    detector_version=ObjectiveCausalDeathsDetector.version,
                    severity=severity,
                    phase=_phase_for(objective["timestamp"]),
                    confidence=1.0,
                    timestamps_s=(death["timestamp"] / 1000.0, objective["timestamp"] / 1000.0),
                    evidence=(
                        Evidence(
                            key="time_since_death_s",
                            label=f"Seconds between death and {monster_type} takedown",
                            value=round((objective["timestamp"] - death["timestamp"]) / 1000.0, 1),
                            unit="seconds",
                        ),
                        Evidence(key="death_cost_s", label="Respawn timer at that death", value=round(cost_s, 1), unit="seconds"),
                        Evidence(
                            key="still_dead_margin_s",
                            label="How long the subject was still dead when the objective fell",
                            value=round(margin_s, 1),
                            unit="seconds",
                        ),
                    ),
                    affected_metrics=("objective_causal_death_count",),
                )
            )

        headline = (Evidence(key="objective_causal_death_count", label="Enemy objectives taken while subject was dead", value=float(len(findings)), unit="count"),)

        if not findings:
            return DetectorResult.clean(ObjectiveCausalDeathsDetector, metrics=headline)

        return DetectorResult.with_findings(ObjectiveCausalDeathsDetector, tuple(findings))


def _causal_death_for(
    objective: dict[str, Any], subject_deaths: list[dict[str, Any]], timeline: Any, subject_id: int
) -> tuple[dict[str, Any], float, float] | None:
    obj_ts = objective["timestamp"]
    candidates = [d for d in subject_deaths if 0 <= obj_ts - d["timestamp"] <= _PRECEDING_WINDOW_MS]
    if not candidates:
        return None
    death = max(candidates, key=lambda d: d["timestamp"])  # most recent qualifying death

    level = timeline.level_at(subject_id, death["timestamp"]) or 1
    cost_s = death_cost_s(level, death["timestamp"] / 1000.0)
    respawn_ready_ts = death["timestamp"] + cost_s * 1000.0
    if respawn_ready_ts < obj_ts:
        return None  # respawned in time -- not a finding

    margin_s = (respawn_ready_ts - obj_ts) / 1000.0
    return death, cost_s, margin_s


def _phase_for(ts_ms: float) -> Phase:
    minute = ts_ms / 60_000.0
    if minute < 14:
        return Phase.EARLY
    if minute < 25:
        return Phase.MID
    return Phase.LATE
