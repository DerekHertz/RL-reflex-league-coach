"""The detector contract.

Detectors are pure, synchronous functions of an AnalysisContext -- no I/O,
no async -- which is what makes them trivially unit-testable with synthetic
timelines and lets the runner isolate failures without special-casing.

The five-outcome model on DetectorResult is the thing most likely to get cut
by mistake, and it is load-bearing: without the CLEAN vs NOT_APPLICABLE
split, the LLM narrator has no way to tell "this detector ran and found
nothing wrong" (praise material) from "this detector doesn't apply to this
game" (ARAM, no lane opponent -- must never be mentioned).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from lolcoach.detectors.context import AnalysisContext


class DataNeed(StrEnum):
    MATCH = "match"
    TIMELINE = "timeline"


class Severity(IntEnum):
    INFO = 0
    MINOR = 1
    MODERATE = 2
    MAJOR = 3


class Phase(StrEnum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"
    WHOLE_GAME = "whole_game"


class PeerKind(StrEnum):
    LANE_OPPONENT = "lane_opponent"
    ROLE_COHORT = "role_cohort"
    TEAM = "team"
    LOBBY = "lobby"
    NONE = "none"


class DetectorOutcome(StrEnum):
    FINDINGS = "findings"
    CLEAN = "clean"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


EvidenceUnit = Literal["gold", "seconds", "percent", "count", "meters", "ratio", "per_minute"]


@dataclass(frozen=True, slots=True)
class Evidence:
    key: str
    label: str
    value: float
    unit: EvidenceUnit
    peer_value: float | None = None
    peer_kind: PeerKind = PeerKind.NONE
    rank_in_lobby: int | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    id: str
    detector_id: str
    detector_version: int
    severity: Severity
    phase: Phase
    confidence: float
    timestamps_s: tuple[float, ...]
    evidence: tuple[Evidence, ...]
    affected_metrics: tuple[str, ...] = ()
    positions: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError(f"Finding {self.id!r} has no evidence -- a finding without numbers is not a finding")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Finding {self.id!r} confidence {self.confidence} out of [0, 1]")


@dataclass(frozen=True, slots=True)
class DetectorResult:
    detector_id: str
    detector_version: int
    outcome: DetectorOutcome
    findings: tuple[Finding, ...] = ()
    reason: str | None = None
    headline_metrics: tuple[Evidence, ...] = ()
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        needs_reason = (DetectorOutcome.NOT_APPLICABLE, DetectorOutcome.INSUFFICIENT_DATA, DetectorOutcome.ERROR)
        if self.outcome in needs_reason and not self.reason:
            raise ValueError(f"{self.outcome} requires a non-empty reason")
        if self.outcome == DetectorOutcome.FINDINGS and not self.findings:
            raise ValueError("FINDINGS outcome requires at least one finding")

    @classmethod
    def clean(cls, detector: type[Detector], *, metrics: tuple[Evidence, ...] = ()) -> DetectorResult:
        return cls(
            detector_id=detector.id, detector_version=detector.version, outcome=DetectorOutcome.CLEAN, headline_metrics=metrics
        )

    @classmethod
    def with_findings(cls, detector: type[Detector], findings: tuple[Finding, ...]) -> DetectorResult:
        return cls(detector_id=detector.id, detector_version=detector.version, outcome=DetectorOutcome.FINDINGS, findings=findings)

    @classmethod
    def na(cls, detector: type[Detector], reason: str) -> DetectorResult:
        return cls(detector_id=detector.id, detector_version=detector.version, outcome=DetectorOutcome.NOT_APPLICABLE, reason=reason)

    @classmethod
    def insufficient(cls, detector: type[Detector], reason: str) -> DetectorResult:
        return cls(
            detector_id=detector.id, detector_version=detector.version, outcome=DetectorOutcome.INSUFFICIENT_DATA, reason=reason
        )

    @classmethod
    def error(cls, detector: type[Detector], reason: str) -> DetectorResult:
        return cls(detector_id=detector.id, detector_version=detector.version, outcome=DetectorOutcome.ERROR, reason=reason)

    def with_duration(self, duration_ms: float) -> DetectorResult:
        return replace(self, duration_ms=duration_ms)


@runtime_checkable
class Detector(Protocol):
    """Detectors are classes, never instantiated -- `run` is a staticmethod
    and every other attribute is class-level declaration data, so the runner
    can pre-filter (skip fetching a timeline nothing needs, skip ARAM-only
    detectors on Arena games) without executing anything.
    """

    id: ClassVar[str]
    version: ClassVar[int]
    title: ClassVar[str]
    needs: ClassVar[frozenset[DataNeed]]
    min_duration_s: ClassVar[int]
    supported_queues: ClassVar[frozenset[int] | None]
    requires_positions: ClassVar[bool]
    emits_metrics: ClassVar[frozenset[str]]

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult: ...
