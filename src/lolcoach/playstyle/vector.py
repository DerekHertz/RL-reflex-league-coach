"""PlaystyleVector -- the pure schema for a player's 6-axis playstyle
profile, computed across their recent cached games (see build.py for the
computation).

Pure schema, mirroring analysis/factsheet.py's split: this module has no
domain/riot imports so it's cheap to import anywhere (API responses,
recommend.py, tests) without pulling in match-parsing machinery.

Every axis is a MEAN of per-game LOBBY PERCENTILE scores (never an absolute
value, never compared across matches) -- see build.py's module docstring for
the exact formula.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

AXES: tuple[str, ...] = (
    "aggression",
    "farming",
    "vision",
    "objective_focus",
    "risk_tolerance",
    "teamfight_vs_split",
)


class PlaystyleVector(BaseModel):
    aggression: float = Field(ge=0.0, le=1.0)
    farming: float = Field(ge=0.0, le=1.0)
    vision: float = Field(ge=0.0, le=1.0)
    objective_focus: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)
    teamfight_vs_split: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
