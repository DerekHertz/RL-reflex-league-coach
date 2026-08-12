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


_WHAT_HAPPENED: dict[str, Callable[[Finding], str]] = {
    "unspent_gold": _what_happened_unspent_gold,
    "time_dead": _what_happened_time_dead,
    "gold_curve_shape": _what_happened_gold_curve_shape,
}


def what_happened(finding: Finding) -> str:
    fn = _WHAT_HAPPENED.get(finding.detector_id)
    if fn is None:
        raise KeyError(f"no what_happened template registered for detector {finding.detector_id!r}")
    return fn(finding)
