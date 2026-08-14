"""Map-coordinate geometry for Summoner's Rift.

Riot does not precisely document map coordinate bounds. The values below are
the community-derived bounds (origin at blue base, bottom-left; y increases
upward toward red base, top-right). Landmark positions (Baron pit, Dragon
pit) are NOT hardcoded from memory -- they are derived empirically from real
match timelines by `scripts/derive_landmarks.py` and loaded from
`data/map_landmarks.json` (see `MapGeometry.load`).

Region classification works entirely from blue's perspective: `side_normalize`
mirrors red-team coordinates through the map center first, so every other
function here (`to_unit_square`, `map_depth`, `MapGeometry.region_of`) only
ever has to reason about one side of the map.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Point = tuple[float, float]

MAP_MIN: Point = (-120.0, -120.0)
MAP_MAX: Point = (14870.0, 14980.0)
MAP_CENTER: Point = ((MAP_MIN[0] + MAP_MAX[0]) / 2.0, (MAP_MIN[1] + MAP_MAX[1]) / 2.0)

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200

# How close a point must be to a derived landmark centroid to count as
# "in the pit" rather than merely "nearby in the river". 1200 units is a
# starting point -- see scripts/derive_landmarks.py's docstring for how it
# was chosen against the 25-match sample.
PIT_RADIUS = 1200.0

# Band widths, all in normalized [0, 1] unit-square units.
_FOUNTAIN_DEPTH = 0.08
_MID_LANE_BAND = 0.10
_RIVER_BAND = 0.12
_LANE_EDGE_BAND = 0.45

_DEFAULT_LANDMARKS_PATH = Path(__file__).resolve().parents[3] / "data" / "map_landmarks.json"


def side_normalize(x: float, y: float, team_id: int) -> Point:
    """Mirror red-team (`team_id=200`) coordinates through the map center so
    every region-classification function only has to be written once, from
    blue's perspective. Blue (`team_id=100`) coordinates pass through
    unchanged.
    """
    if team_id == RED_TEAM_ID:
        return (2 * MAP_CENTER[0] - x, 2 * MAP_CENTER[1] - y)
    return (x, y)


def to_unit_square(x: float, y: float) -> tuple[float, float]:
    """Normalize side-normalized coordinates to (u, v) in [0, 1]."""
    u = (x - MAP_MIN[0]) / (MAP_MAX[0] - MAP_MIN[0])
    v = (y - MAP_MIN[1]) / (MAP_MAX[1] - MAP_MIN[1])
    return (u, v)


def map_depth(u: float, v: float) -> float:
    """0 = own fountain, 1 = enemy fountain."""
    return (u + v) / 2.0


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass(frozen=True, slots=True)
class Landmark:
    name: str
    centroid: Point
    sample_count: int


@dataclass(frozen=True, slots=True)
class MapGeometry:
    """Region classifier plus the empirically-derived landmark centroids it
    checks against. Construct via `MapGeometry.load()` in production code;
    the bare constructor is mainly useful for tests that want to supply
    synthetic landmarks.
    """

    baron_pit: Landmark
    dragon_pit: Landmark
    pit_radius: float = PIT_RADIUS

    @classmethod
    def load(cls, path: Path | None = None) -> MapGeometry:
        path = path or _DEFAULT_LANDMARKS_PATH
        data: dict[str, Any] = json.loads(path.read_text())
        landmarks = data["landmarks"]
        return cls(
            baron_pit=Landmark("baron_pit", tuple(landmarks["baron_pit"]["centroid"]), landmarks["baron_pit"]["sample_count"]),
            dragon_pit=Landmark("dragon_pit", tuple(landmarks["dragon_pit"]["centroid"]), landmarks["dragon_pit"]["sample_count"]),
        )

    def region_of(self, x: float, y: float, team_id: int) -> str:
        """Classify a raw map position into a coarse region name, from the
        given team's perspective (so "own_fountain"/"enemy_fountain" and the
        jungle-half names are relative to `team_id`, not absolute blue/red).
        """
        nx, ny = side_normalize(x, y, team_id)

        if _distance((nx, ny), self.baron_pit.centroid) <= self.pit_radius:
            return "baron_pit"
        if _distance((nx, ny), self.dragon_pit.centroid) <= self.pit_radius:
            return "dragon_pit"

        u, v = to_unit_square(nx, ny)
        depth = map_depth(u, v)
        s = v - u  # main-diagonal offset: >0 top half, <0 bottom half
        d = u + v - 1.0  # anti-diagonal offset: <0 own half, >0 enemy half

        if depth <= _FOUNTAIN_DEPTH:
            return "own_fountain"
        if depth >= 1.0 - _FOUNTAIN_DEPTH:
            return "enemy_fountain"

        if abs(s) <= _MID_LANE_BAND:
            return "mid_lane"

        if abs(d) <= _RIVER_BAND:
            return "river"

        if s > 0:
            if s >= _LANE_EDGE_BAND:
                return "top_lane"
            return "own_top_jungle" if d < 0 else "enemy_top_jungle"

        if -s >= _LANE_EDGE_BAND:
            return "bot_lane"
        return "own_bot_jungle" if d < 0 else "enemy_bot_jungle"
