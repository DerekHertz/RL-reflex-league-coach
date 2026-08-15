"""Detects where on the map a player tends to die.

Two related signals live here: (1) a single region accounting for a large
share of deaths (e.g. "you die in the enemy bot jungle constantly") and (2)
"deep" deaths -- dying far from home with no objective (dragon/baron/turret)
taken nearby to explain the risk. Both read from `CHAMPION_KILL.position`,
side-normalized by the SUBJECT's team so region names are always relative to
the subject ("enemy_bot_jungle" means the enemy's bot jungle, regardless of
which raw team_id the subject is on).
"""

from __future__ import annotations

from collections import Counter
from typing import Any, ClassVar

from lolcoach.detectors.base import DataNeed, DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.context import AnalysisContext
from lolcoach.domain.geometry import MapGeometry, map_depth, side_normalize, to_unit_square

_MIN_DEATHS = 3
_CONCENTRATION_THRESHOLD = 0.40
_CONCENTRATION_MAJOR = 0.60
# A region's deaths only count as "concentrated" if they also happened close
# together in time -- two deaths in the same region 25 minutes apart in a
# 30-minute game are unrelated events, not a pattern, even if that region is
# a majority share of a low total death count. This is a ratio of the
# region's own death-timestamp span to total game duration, not a fixed
# death-count floor: it scales with however long the game ran.
_CONCENTRATION_MAX_TIME_SPAN_RATIO = 0.5
_DEEP_DEPTH_THRESHOLD = 0.6
_DEEP_DEATH_SHARE_THRESHOLD = 0.40
_OBJECTIVE_WINDOW_MS = 60_000


class DeathRegionsDetector:
    id: ClassVar[str] = "death_regions"
    version: ClassVar[int] = 1
    title: ClassVar[str] = "Where you die"
    needs: ClassVar[frozenset[DataNeed]] = frozenset({DataNeed.TIMELINE})
    min_duration_s: ClassVar[int] = 600
    supported_queues: ClassVar[frozenset[int] | None] = None
    requires_positions: ClassVar[bool] = True
    emits_metrics: ClassVar[frozenset[str]] = frozenset({"death_region_concentration", "deep_death_share"})

    @staticmethod
    def run(ctx: AnalysisContext) -> DetectorResult:
        assert ctx.timeline is not None
        deaths = [e for e in ctx.timeline.events_of_type("CHAMPION_KILL") if e.get("victimId") == ctx.subject.participant_id]
        deaths = [d for d in deaths if d.get("position")]

        if len(deaths) < _MIN_DEATHS:
            return DetectorResult.na(
                DeathRegionsDetector, f"fewer than {_MIN_DEATHS} deaths with a recorded position ({len(deaths)} found)"
            )

        geo = MapGeometry.load()
        objective_timestamps = [
            e["timestamp"] for e in ctx.timeline.events_of_type("ELITE_MONSTER_KILL") + ctx.timeline.events_of_type("BUILDING_KILL")
        ]

        regions: list[str] = []
        normalized_positions: list[tuple[float, float]] = []
        deep_deaths: list[dict[str, Any]] = []
        for death in deaths:
            raw_x, raw_y = death["position"]["x"], death["position"]["y"]
            nx, ny = side_normalize(raw_x, raw_y, ctx.subject.team_id)
            normalized_positions.append((nx, ny))
            regions.append(geo.region_of(raw_x, raw_y, ctx.subject.team_id))

            u, v = to_unit_square(nx, ny)
            depth = map_depth(u, v)
            if depth > _DEEP_DEPTH_THRESHOLD and not _near_objective(death["timestamp"], objective_timestamps):
                deep_deaths.append(death)

        total = len(deaths)
        region_counts = Counter(regions)
        top_region, top_count = region_counts.most_common(1)[0]
        region_share = top_count / total
        deep_share = len(deep_deaths) / total

        headline = (
            Evidence(
                key="death_region_concentration",
                label=f"Share of deaths in {top_region}",
                value=round(region_share * 100, 1),
                unit="percent",
            ),
            Evidence(key="deep_death_share", label="Share of deaths deep with no nearby objective", value=round(deep_share * 100, 1), unit="percent"),
        )

        findings: list[Finding] = []

        region_death_timestamps = tuple(
            d["timestamp"] / 1000.0 for d, r in zip(deaths, regions, strict=True) if r == top_region
        )
        region_time_span_ratio = (max(region_death_timestamps) - min(region_death_timestamps)) / ctx.match.duration_s

        if region_share >= _CONCENTRATION_THRESHOLD and region_time_span_ratio <= _CONCENTRATION_MAX_TIME_SPAN_RATIO:
            region_positions = tuple(p for p, r in zip(normalized_positions, regions, strict=True) if r == top_region)
            severity = Severity.MAJOR if region_share >= _CONCENTRATION_MAJOR else Severity.MODERATE
            findings.append(
                Finding(
                    id="death_regions:concentration",
                    detector_id=DeathRegionsDetector.id,
                    detector_version=DeathRegionsDetector.version,
                    severity=severity,
                    phase=Phase.WHOLE_GAME,
                    confidence=1.0,
                    timestamps_s=region_death_timestamps,
                    evidence=(
                        Evidence(key="top_region", label="Most common death region", value=float(top_count), unit="count"),
                        Evidence(
                            key="death_region_concentration",
                            label=f"Share of deaths in {top_region}",
                            value=round(region_share * 100, 1),
                            unit="percent",
                        ),
                        Evidence(key="death_count", label="Total deaths considered", value=float(total), unit="count"),
                        Evidence(key="deep_death_share", label="Share of deaths deep with no nearby objective", value=round(deep_share * 100, 1), unit="percent"),
                    ),
                    affected_metrics=("death_region_concentration",),
                    positions=region_positions,
                )
            )

        if deep_share >= _DEEP_DEATH_SHARE_THRESHOLD and region_share < _CONCENTRATION_THRESHOLD:
            deep_timestamps = tuple(d["timestamp"] / 1000.0 for d in deep_deaths)
            deep_positions = tuple(
                side_normalize(d["position"]["x"], d["position"]["y"], ctx.subject.team_id) for d in deep_deaths
            )
            severity = Severity.MAJOR if deep_share >= 0.6 else Severity.MODERATE
            findings.append(
                Finding(
                    id="death_regions:deep",
                    detector_id=DeathRegionsDetector.id,
                    detector_version=DeathRegionsDetector.version,
                    severity=severity,
                    phase=Phase.WHOLE_GAME,
                    confidence=1.0,
                    timestamps_s=deep_timestamps,
                    evidence=(
                        Evidence(key="deep_death_count", label="Deep deaths with no nearby objective", value=float(len(deep_deaths)), unit="count"),
                        Evidence(
                            key="deep_death_share",
                            label="Share of deaths deep with no nearby objective",
                            value=round(deep_share * 100, 1),
                            unit="percent",
                        ),
                        Evidence(key="death_count", label="Total deaths considered", value=float(total), unit="count"),
                    ),
                    affected_metrics=("deep_death_share",),
                    positions=deep_positions,
                )
            )

        if not findings:
            return DetectorResult.clean(DeathRegionsDetector, metrics=headline)

        return DetectorResult.with_findings(DeathRegionsDetector, tuple(findings))


def _near_objective(death_ts_ms: int, objective_timestamps: list[int]) -> bool:
    return any(abs(death_ts_ms - obj_ts) <= _OBJECTIVE_WINDOW_MS for obj_ts in objective_timestamps)
