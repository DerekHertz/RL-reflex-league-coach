"""The detector registry: an explicit tuple, not auto-discovery.

"Pluggable" means a clean interface (base.Detector), not dynamic loading --
an explicit tuple is greppable, ordered, and type-checked.
"""

import hashlib

from lolcoach.detectors.base import Detector
from lolcoach.detectors.gold_curve_shape import GoldCurveShapeDetector
from lolcoach.detectors.time_dead import TimeDeadDetector
from lolcoach.detectors.unspent_gold import UnspentGoldDetector

DETECTORS: tuple[type[Detector], ...] = (
    UnspentGoldDetector,
    TimeDeadDetector,
    GoldCurveShapeDetector,
)


def engine_version() -> str:
    """A short hash of (detector id, version) pairs. Bumping any detector's
    `version` changes this, which changes AnalysisRun's cache key -- so a
    detector-logic change writes a NEW cached analysis alongside the old one
    rather than silently serving stale results.
    """
    key = "|".join(f"{d.id}:{d.version}" for d in sorted(DETECTORS, key=lambda d: d.id))
    return hashlib.sha1(key.encode()).hexdigest()[:12]
