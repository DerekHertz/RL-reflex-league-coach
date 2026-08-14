"""Derives empirical Baron/Dragon pit centroids from cached real timelines.

Map coordinates aren't precisely documented by Riot, so rather than hardcode
landmark positions from memory, this walks every cached timeline this repo
has locally (`cache/timeline/**/*.json.gz`), pulls every ELITE_MONSTER_KILL
event, groups positions by `monsterType`, and averages them.

Baron Nashor and Rift Herald share a pit, so their samples are pooled into a
single `baron_pit` landmark. Dragon (all sub-types -- air/earth/fire/water/
chemtech/hextech) gets its own `dragon_pit` landmark. Other monster types
(HORDE/Void Grubs, ATAKHAN) are recorded in the output for visibility but
don't currently back a named region in MapGeometry.

Run: `uv run python scripts/derive_landmarks.py`
"""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TIMELINE_CACHE = _REPO_ROOT / "cache" / "timeline"
_OUTPUT_PATH = _REPO_ROOT / "data" / "map_landmarks.json"

_MIN_SAMPLES = 3

# monsterType values that together occupy the same physical pit as Baron
# Nashor (Rift Herald spawns in the Baron pit before Baron does).
_BARON_PIT_TYPES = {"BARON_NASHOR", "RIFTHERALD"}
_DRAGON_PIT_TYPES = {"DRAGON"}


def _load_timeline_raw(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _iter_elite_monster_kills(raw: dict[str, Any]):
    for frame in raw["info"]["frames"]:
        for event in frame.get("events", []):
            if event.get("type") == "ELITE_MONSTER_KILL":
                yield event


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def main() -> None:
    from lolcoach.domain.timeline import TimelineIndex  # reuse the shared timeline parser

    files = sorted(_TIMELINE_CACHE.glob("*/*.json.gz"))
    if not files:
        print(f"No cached timelines found under {_TIMELINE_CACHE}")
        return

    positions_by_type: dict[str, list[tuple[float, float]]] = defaultdict(list)
    matches_seen = 0

    for path in files:
        raw = _load_timeline_raw(path)
        # Round-trip through TimelineIndex rather than hand-rolling the
        # frame/event walk, per the shared-parser convention this repo uses
        # everywhere else a timeline is touched.
        index = TimelineIndex(raw)
        matches_seen += 1
        for event in index.events_of_type("ELITE_MONSTER_KILL"):
            monster_type = event.get("monsterType")
            pos = event.get("position")
            if not monster_type or not pos:
                continue
            positions_by_type[monster_type].append((pos["x"], pos["y"]))

    print(f"Scanned {matches_seen} cached timelines from {_TIMELINE_CACHE}")
    print()
    print("Raw monsterType sample counts:")
    for monster_type, points in sorted(positions_by_type.items(), key=lambda kv: -len(kv[1])):
        cx, cy = _centroid(points)
        print(f"  {monster_type:15s} n={len(points):3d}  centroid=({cx:.0f}, {cy:.0f})")

    baron_points = [p for t in _BARON_PIT_TYPES for p in positions_by_type.get(t, [])]
    dragon_points = [p for t in _DRAGON_PIT_TYPES for p in positions_by_type.get(t, [])]

    landmarks: dict[str, Any] = {}
    warnings: list[str] = []

    for name, points, source_types in (
        ("baron_pit", baron_points, _BARON_PIT_TYPES),
        ("dragon_pit", dragon_points, _DRAGON_PIT_TYPES),
    ):
        if len(points) < _MIN_SAMPLES:
            warnings.append(
                f"{name}: only {len(points)} samples (< {_MIN_SAMPLES}) from types {sorted(source_types)} -- "
                "centroid may be unreliable"
            )
        if points:
            cx, cy = _centroid(points)
            landmarks[name] = {
                "centroid": [round(cx, 1), round(cy, 1)],
                "sample_count": len(points),
                "source_monster_types": sorted(source_types & positions_by_type.keys()),
            }
        else:
            warnings.append(f"{name}: zero samples from types {sorted(source_types)} -- landmark NOT written")

    other_types = {t: len(v) for t, v in positions_by_type.items() if t not in _BARON_PIT_TYPES | _DRAGON_PIT_TYPES}

    output = {
        "derived_from_n_matches": matches_seen,
        "landmarks": landmarks,
        "other_monster_types_observed": other_types,
    }

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n")

    print()
    print(f"Wrote {_OUTPUT_PATH} derived from {matches_seen} matches:")
    for name, lm in landmarks.items():
        print(f"  {name}: centroid={tuple(lm['centroid'])} n={lm['sample_count']} from {lm['source_monster_types']}")
    if other_types:
        print(f"  (other monster types observed but not used as landmarks: {other_types})")

    if warnings:
        print()
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
