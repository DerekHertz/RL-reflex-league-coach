"""Runs the detector registry against a context.

Pre-filters on declared preconditions (needs/min_duration_s/supported_queues)
before ever calling `run()`, and isolates every detector's execution so one
misbehaving detector can never fail an entire analysis.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from lolcoach.detectors.base import DataNeed, Detector, DetectorOutcome, DetectorResult
from lolcoach.detectors.context import AnalysisContext


def run_detectors(ctx: AnalysisContext, detectors: Sequence[type[Detector]]) -> list[DetectorResult]:
    results: list[DetectorResult] = []
    for detector in detectors:
        na_reason = _precondition_failure(ctx, detector)
        if na_reason is not None:
            results.append(DetectorResult.na(detector, na_reason))
            continue

        start = time.monotonic()
        try:
            result = detector.run(ctx)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: isolate detector failures
            result = DetectorResult.error(detector, f"{type(exc).__name__}: {exc}")
        duration_ms = (time.monotonic() - start) * 1000
        results.append(result.with_duration(duration_ms))

    return results


def _precondition_failure(ctx: AnalysisContext, detector: type[Detector]) -> str | None:
    if DataNeed.TIMELINE in detector.needs and ctx.timeline is None:
        return "timeline data not available for this match"
    if ctx.match.duration_s < detector.min_duration_s:
        return f"game duration {ctx.match.duration_s:.0f}s is below the detector's minimum {detector.min_duration_s}s"
    if detector.supported_queues is not None and ctx.match.queue_id not in detector.supported_queues:
        return f"queue {ctx.match.queue_id} is not supported by this detector"
    return None
