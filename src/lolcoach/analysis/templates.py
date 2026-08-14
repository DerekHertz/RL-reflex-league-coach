"""Deterministic prose for facts -- NOT the LLM's job.

Every `what_happened` sentence a Finding carries is generated here, from the
finding's own evidence values, with pre-formatted timestamps. This is what
lets the LLM narrate rather than invent: it never does arithmetic and never
describes what occurred, only why it matters and what to do differently.
"""

from __future__ import annotations

from collections.abc import Callable

from lolcoach.detectors.base import Finding

TITLES: dict[str, str] = {
    "unspent_gold": "Sitting on gold",
    "time_dead": "Time spent dead",
    "gold_curve_shape": "Lost a lane lead",
    "death_regions": "Where you die",
    "ward_drought": "Ward drought",
    "isolation_at_death": "Caught out alone",
    "objective_causal_deaths": "Deaths that gave up objectives",
}


def format_timestamp_s(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _evidence_value(finding: Finding, key: str) -> float | None:
    for e in finding.evidence:
        if e.key == key:
            return e.value
    return None


def _what_happened_unspent_gold(finding: Finding) -> str:
    peak = _evidence_value(finding, "peak_gold") or 0.0
    duration = _evidence_value(finding, "run_duration_min") or 0.0
    start = format_timestamp_s(finding.timestamps_s[0]) if finding.timestamps_s else "?"
    return (
        f"Starting around {start}, unspent gold reached {peak:.0f} and stayed above "
        f"1400 for about {duration:.1f} minutes."
    )


def _what_happened_time_dead(finding: Finding) -> str:
    share = _evidence_value(finding, "time_dead_share") or 0.0
    deaths = _evidence_value(finding, "death_count") or 0.0
    return f"{share:.1f}% of the game was spent dead, across {deaths:.0f} deaths."


def _what_happened_gold_curve_shape(finding: Finding) -> str:
    gd15 = _evidence_value(finding, "gold_diff_at_15") or 0.0
    gd25 = _evidence_value(finding, "gold_diff_at_25") or 0.0
    lost = _evidence_value(finding, "lead_lost") or 0.0
    return (
        f"A {gd15:.0f} gold lead over the lane opponent at 15 minutes had shrunk to "
        f"{gd25:.0f} by 25 minutes -- a swing of {lost:.0f} gold."
    )


def _what_happened_death_regions(finding: Finding) -> str:
    if finding.id.endswith(":deep"):
        count = _evidence_value(finding, "deep_death_count") or 0.0
        share = _evidence_value(finding, "deep_death_share") or 0.0
        total = _evidence_value(finding, "death_count") or 0.0
        return (
            f"{count:.0f} of {total:.0f} deaths ({share:.1f}%) happened deep in enemy territory with no "
            f"objective taken nearby to explain the risk."
        )
    concentration = next((e for e in finding.evidence if e.key == "death_region_concentration"), None)
    region_label = concentration.label.removeprefix("Share of deaths in ") if concentration else "one region"
    share = concentration.value if concentration else 0.0
    total = _evidence_value(finding, "death_count") or 0.0
    top_count = _evidence_value(finding, "top_region") or 0.0
    return f"{top_count:.0f} of {total:.0f} deaths ({share:.1f}%) happened in {region_label}."


def _what_happened_ward_drought(finding: Finding) -> str:
    gap = _evidence_value(finding, "max_ward_gap_s") or 0.0
    threshold = _evidence_value(finding, "threshold_s") or 0.0
    start = format_timestamp_s(finding.timestamps_s[0]) if finding.timestamps_s else "?"
    end = format_timestamp_s(finding.timestamps_s[1]) if len(finding.timestamps_s) > 1 else "?"
    return (
        f"No wards were placed between {start} and {end}, a {gap:.0f}s gap (threshold for this role is "
        f"{threshold:.0f}s)."
    )


def _what_happened_isolation_at_death(finding: Finding) -> str:
    dist = _evidence_value(finding, "nearest_ally_dist") or 0.0
    depth = _evidence_value(finding, "map_depth") or 0.0
    ts = format_timestamp_s(finding.timestamps_s[0]) if finding.timestamps_s else "?"
    return (
        f"At {ts}, the nearest ally was {dist:.0f} units away while positioned deep in enemy territory "
        f"(map depth {depth:.2f})."
    )


def _what_happened_objective_causal_deaths(finding: Finding) -> str:
    time_since = next((e for e in finding.evidence if e.key == "time_since_death_s"), None)
    monster_label = time_since.label.removeprefix("Seconds between death and ").removesuffix(" takedown") if time_since else "the objective"
    time_since_val = time_since.value if time_since else 0.0
    margin = _evidence_value(finding, "still_dead_margin_s") or 0.0
    return (
        f"Died {time_since_val:.0f}s before {monster_label} was taken, and was still on the respawn timer "
        f"with {margin:.0f}s left when it fell."
    )


_WHAT_HAPPENED: dict[str, Callable[[Finding], str]] = {
    "unspent_gold": _what_happened_unspent_gold,
    "time_dead": _what_happened_time_dead,
    "gold_curve_shape": _what_happened_gold_curve_shape,
    "death_regions": _what_happened_death_regions,
    "ward_drought": _what_happened_ward_drought,
    "isolation_at_death": _what_happened_isolation_at_death,
    "objective_causal_deaths": _what_happened_objective_causal_deaths,
}


def what_happened(finding: Finding) -> str:
    fn = _WHAT_HAPPENED.get(finding.detector_id)
    if fn is None:
        raise KeyError(f"no what_happened template registered for detector {finding.detector_id!r}")
    return fn(finding)
