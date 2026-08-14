"""Builds a MatchFactSheet from an AnalysisContext + DetectorResults.

This is the domain-facing half of the anonymization boundary (see
factsheet.py's module docstring for why the schema and the builder are
split into separate modules). `lolcoach.llm` must never import this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from lolcoach.analysis.factsheet import (
    NOT_KNOWABLE,
    CleanCheck,
    EvidenceFact,
    FindingFact,
    MatchFactSheet,
    MatchMeta,
    MetricComparison,
    MetricFact,
    OpponentFacts,
    SkillScore,
    SkippedCheck,
    SubjectFacts,
)
from lolcoach.analysis.templates import TITLES, format_timestamp_s, what_happened
from lolcoach.detectors.base import DetectorOutcome, DetectorResult, Evidence, Finding, PeerKind, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.domain.match import PeerComparison
from lolcoach.metrics.combat import time_dead_share
from lolcoach.metrics.economy import cs_per_minute, gold_per_minute

_QUEUE_NAMES: dict[int, str] = {
    400: "Normal Draft",
    420: "Ranked Solo/Duo",
    430: "Normal Blind",
    440: "Ranked Flex",
    450: "ARAM",
    700: "Clash",
    1700: "Arena",
    1710: "Arena",
}

_SKILL_DETECTOR_MAP: dict[str, tuple[str, ...]] = {
    "economy": ("unspent_gold", "gold_curve_shape"),
    "survivability": ("time_dead", "death_regions", "isolation_at_death"),
    "vision": ("ward_drought",),
    "objectives": ("objective_causal_deaths",),
}


def build_fact_sheet(ctx: AnalysisContext, detector_results: Sequence[DetectorResult]) -> MatchFactSheet:
    opponent = None
    if ctx.peers.lane_opponent is not None:
        opponent = OpponentFacts(
            champion=ctx.peers.lane_opponent.champion_name,
            role=ctx.peers.lane_opponent.team_position or "unknown",
        )

    findings: list[FindingFact] = []
    clean_checks: list[CleanCheck] = []
    skipped_checks: list[SkippedCheck] = []

    for result in detector_results:
        if result.outcome == DetectorOutcome.FINDINGS:
            findings.extend(_finding_fact(f) for f in result.findings)
        elif result.outcome == DetectorOutcome.CLEAN:
            clean_checks.append(_clean_check(result))
        elif result.outcome in (DetectorOutcome.NOT_APPLICABLE, DetectorOutcome.INSUFFICIENT_DATA):
            skipped_checks.append(
                SkippedCheck(check=TITLES.get(result.detector_id, result.detector_id), reason=result.reason or "")
            )
        # ERROR outcomes are telemetry-only and never reach the fact sheet.

    return MatchFactSheet(
        subject=SubjectFacts(champion=ctx.subject.champion_name, role=ctx.subject.team_position or "unknown"),
        match=MatchMeta(
            queue_name=_queue_name(ctx.match.queue_id),
            patch=_patch(ctx.match.game_version),
            duration=format_timestamp_s(ctx.match.duration_s),
            result="win" if ctx.subject.win else "loss",
            team_side="blue" if ctx.subject.team_id == 100 else "red",
        ),
        lane_opponent=opponent,
        metrics=_build_metrics(ctx),
        findings=findings,
        clean_checks=clean_checks,
        skipped_checks=skipped_checks,
        skill_scores=_build_skill_scores(detector_results),
        not_knowable=list(NOT_KNOWABLE),
    )


def _queue_name(queue_id: int) -> str:
    return _QUEUE_NAMES.get(queue_id, f"Queue {queue_id}")


def _patch(game_version: str) -> str:
    parts = game_version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else game_version


def _evidence_fact(e: Evidence) -> EvidenceFact:
    return EvidenceFact(
        label=e.label,
        value=e.value,
        unit=e.unit,
        peer_value=e.peer_value,
        peer_label=e.peer_kind.value if e.peer_kind != PeerKind.NONE else None,
    )


def _finding_fact(f: Finding) -> FindingFact:
    return FindingFact(
        id=f.id,
        title=TITLES.get(f.detector_id, f.detector_id),
        severity=f.severity.name.lower(),  # type: ignore[arg-type]
        phase=f.phase.value,  # type: ignore[arg-type]
        confidence=f.confidence,
        what_happened=what_happened(f),
        timestamps=[format_timestamp_s(t) for t in f.timestamps_s],
        evidence=[_evidence_fact(e) for e in f.evidence],
    )


def _clean_check(result: DetectorResult) -> CleanCheck:
    return CleanCheck(
        id=result.detector_id,
        title=TITLES.get(result.detector_id, result.detector_id),
        evidence=[_evidence_fact(e) for e in result.headline_metrics],
    )


def _metric_comparison(cmp: PeerComparison, peer_label: Literal["lane_opponent", "role_cohort_avg"]) -> list[MetricComparison]:
    if cmp.peer_value is None:
        return []
    return [
        MetricComparison(
            peer=peer_label,
            peer_value=round(cmp.peer_value, 1),
            delta=round(cmp.delta, 1) if cmp.delta is not None else 0.0,
            rank_in_lobby=cmp.rank_in_lobby,
        )
    ]


def _build_metrics(ctx: AnalysisContext) -> list[MetricFact]:
    metrics: list[MetricFact] = []
    duration_s = ctx.match.duration_s

    gpm_cmp = ctx.peers.compare(lambda p: gold_per_minute(p, duration_s), higher_is_better=True, peer="role_cohort")
    if gpm_cmp.metric_value is not None:
        metrics.append(
            MetricFact(
                id="gold_per_minute",
                label="Gold per minute",
                value=round(gpm_cmp.metric_value, 0),
                unit="per_minute",
                direction="higher_better",
                comparisons=_metric_comparison(gpm_cmp, "role_cohort_avg"),
            )
        )

    csm_cmp = ctx.peers.compare(lambda p: cs_per_minute(p, duration_s), higher_is_better=True, peer="lane_opponent")
    if csm_cmp.metric_value is not None:
        metrics.append(
            MetricFact(
                id="cs_per_minute",
                label="CS per minute",
                value=round(csm_cmp.metric_value, 1),
                unit="per_minute",
                direction="higher_better",
                comparisons=_metric_comparison(csm_cmp, "lane_opponent"),
            )
        )

    dead_cmp = ctx.peers.compare(
        lambda p: time_dead_share(p.total_time_spent_dead_s, duration_s) * 100,
        higher_is_better=False,
        peer="role_cohort",
    )
    if dead_cmp.metric_value is not None:
        metrics.append(
            MetricFact(
                id="time_dead_share",
                label="Share of game spent dead",
                value=round(dead_cmp.metric_value, 1),
                unit="percent",
                direction="lower_better",
                comparisons=_metric_comparison(dead_cmp, "role_cohort_avg"),
            )
        )

    return metrics


def _build_skill_scores(detector_results: Sequence[DetectorResult]) -> list[SkillScore]:
    """Conservative by construction: a skill only ever reads "below_lobby" or
    "at_lobby". We have no positive-outperformance signal yet (that needs
    the M6+ detector set), so "above_lobby" is never emitted in v1.
    """
    by_id = {r.detector_id: r for r in detector_results}
    scores: list[SkillScore] = []
    for skill, detector_ids in _SKILL_DETECTOR_MAP.items():
        relevant = [by_id[d] for d in detector_ids if d in by_id]
        applicable = [r for r in relevant if r.outcome in (DetectorOutcome.FINDINGS, DetectorOutcome.CLEAN)]
        if not applicable:
            continue
        worst = max((f.severity for r in applicable for f in r.findings), default=None)
        band: Literal["below_lobby", "at_lobby"] = "below_lobby" if worst is not None and worst >= Severity.MODERATE else "at_lobby"
        scores.append(SkillScore(skill=skill, band=band, basis=[r.detector_id for r in applicable]))  # type: ignore[list-item]
    return scores
