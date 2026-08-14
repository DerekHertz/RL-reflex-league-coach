"""Hand-authored champion archetypes -- axis/salience values reflecting the
champion's actual kit and role identity, not win-rate data.

Riot's API has no win-rate/tier data, and scraping third-party sites for it
is against their ToS, so this data is hand-authored from League of Legends
domain knowledge (this is a legitimate, documented project decision, not a
placeholder). See data/champion_archetypes.yaml for the actual roster.

Validation is intentionally strict and fails LOUDLY (raises) rather than
warning: this is data the maintainer controls, so a validation failure means
a data-entry mistake, not a runtime condition callers should route around.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from lolcoach.playstyle.vector import AXES

TeamPosition = Literal["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
VALID_ROLES: tuple[TeamPosition, ...] = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
MIN_CHAMPIONS_PER_ROLE = 6

# Repo-root/data/champion_archetypes.yaml -- this file lives at
# src/lolcoach/playstyle/archetypes.py, so parents[3] is the repo root.
DEFAULT_ARCHETYPES_PATH = Path(__file__).resolve().parents[3] / "data" / "champion_archetypes.yaml"


class ChampionAxes(BaseModel):
    aggression: float = Field(ge=0.0, le=1.0)
    farming: float = Field(ge=0.0, le=1.0)
    vision: float = Field(ge=0.0, le=1.0)
    objective_focus: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)
    teamfight_vs_split: float = Field(ge=0.0, le=1.0)

    def get(self, axis: str) -> float:
        return getattr(self, axis)


class ChampionSalience(BaseModel):
    aggression: float = Field(ge=0.0)
    farming: float = Field(ge=0.0)
    vision: float = Field(ge=0.0)
    objective_focus: float = Field(ge=0.0)
    risk_tolerance: float = Field(ge=0.0)
    teamfight_vs_split: float = Field(ge=0.0)

    def get(self, axis: str) -> float:
        return getattr(self, axis)


class ChampionArchetype(BaseModel):
    name: str
    roles: list[TeamPosition] = Field(min_length=1)
    axes: ChampionAxes
    salience: ChampionSalience
    identity: str


def load_archetypes(path: Path | str = DEFAULT_ARCHETYPES_PATH) -> list[ChampionArchetype]:
    """Load and VALIDATE the champion archetype roster. Raises on any
    problem -- malformed YAML, an axis/salience out of [0, 1)/[0,inf) range,
    an unrecognized role, or a role with fewer than MIN_CHAMPIONS_PER_ROLE
    champions once loaded -- rather than warning and continuing.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"expected a non-empty list of champion entries in {path}")

    archetypes = [ChampionArchetype.model_validate(entry) for entry in raw]

    names = [a.name for a in archetypes]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"duplicate champion name(s) in {path}: {sorted(duplicates)}")

    _validate_role_coverage(archetypes, source=str(path))
    return archetypes


def _validate_role_coverage(archetypes: list[ChampionArchetype], *, source: str) -> None:
    counts: dict[str, int] = {role: 0 for role in VALID_ROLES}
    for archetype in archetypes:
        for role in archetype.roles:
            counts[role] += 1
    under_covered = {role: n for role, n in counts.items() if n < MIN_CHAMPIONS_PER_ROLE}
    if under_covered:
        raise ValueError(
            f"{source}: role(s) with fewer than {MIN_CHAMPIONS_PER_ROLE} champions: {under_covered}"
        )


@lru_cache
def get_default_archetypes() -> tuple[ChampionArchetype, ...]:
    """Cached load of the real data/champion_archetypes.yaml -- callers that
    just want the roster (recommend.py's API-facing caller) use this instead
    of re-parsing YAML on every request.
    """
    return tuple(load_archetypes(DEFAULT_ARCHETYPES_PATH))


__all__ = [
    "AXES",
    "MIN_CHAMPIONS_PER_ROLE",
    "VALID_ROLES",
    "ChampionArchetype",
    "ChampionAxes",
    "ChampionSalience",
    "get_default_archetypes",
    "load_archetypes",
]
