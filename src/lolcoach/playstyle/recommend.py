"""Deterministic, fast champion recommendations from a PlaystyleVector +
the hand-authored archetype roster. No LLM call anywhere in this module --
matches the codebase's rule (see analysis/templates.py) that anything that
can be computed deterministically should be, so the LLM boundary only ever
carries judgement Claude is actually adding.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from lolcoach.playstyle.archetypes import AXES, ChampionArchetype
from lolcoach.playstyle.vector import PlaystyleVector

_AXIS_LABELS: dict[str, str] = {
    "aggression": "aggression",
    "farming": "farming",
    "vision": "vision control",
    "objective_focus": "objective focus",
    "risk_tolerance": "risk tolerance",
    "teamfight_vs_split": "teamfighting vs. split-pushing",
}

# How close a player/archetype axis pair has to be (in the 0..1 axis space)
# to count as a "match" worth calling out in matched_axes.
_MATCH_THRESHOLD = 0.2
_MAX_MATCHED_AXES = 3


class ChampionRec(BaseModel):
    champion: str
    roles: list[str]
    fit_score: float
    kind: Literal["comfort", "stretch"]
    matched_axes: list[str]
    stretch_axis: str | None = None
    rationale: str


def _weighted_cosine(player: PlaystyleVector, archetype: ChampionArchetype, *, skip_axis: str | None = None) -> float:
    numerator = 0.0
    player_sq = 0.0
    archetype_sq = 0.0
    for axis in AXES:
        if axis == skip_axis:
            continue
        weight = archetype.salience.get(axis)
        p = getattr(player, axis)
        a = archetype.axes.get(axis)
        numerator += weight * p * a
        player_sq += weight * p * p
        archetype_sq += weight * a * a
    if player_sq <= 0 or archetype_sq <= 0:
        return 0.0
    return numerator / (math.sqrt(player_sq) * math.sqrt(archetype_sq))


def _weakest_axis(player: PlaystyleVector, archetype: ChampionArchetype) -> str:
    """The single axis where this archetype most diverges from the player,
    weighted by how much that axis defines the archetype's identity
    (salience) -- a big gap on an axis the champion doesn't care about is
    less "divergent" than a smaller gap on its signature axis.
    """
    return max(
        AXES,
        key=lambda axis: archetype.salience.get(axis) * abs(getattr(player, axis) - archetype.axes.get(axis)),
    )


def _matched_axes(player: PlaystyleVector, archetype: ChampionArchetype) -> list[str]:
    candidates = [
        axis
        for axis in AXES
        if abs(getattr(player, axis) - archetype.axes.get(axis)) <= _MATCH_THRESHOLD
    ]
    candidates.sort(key=lambda axis: archetype.salience.get(axis), reverse=True)
    return candidates[:_MAX_MATCHED_AXES]


def _rationale(archetype: ChampionArchetype, *, matched_axes: list[str], stretch_axis: str | None) -> str:
    identity = archetype.identity.rstrip(".")
    if stretch_axis is not None:
        axis_label = _AXIS_LABELS[stretch_axis]
        return f"{identity}. A stretch pick: strong fit everywhere except {axis_label}, where trying this champion means growing that side of your game."
    if matched_axes:
        labels = ", ".join(_AXIS_LABELS[axis] for axis in matched_axes)
        return f"{identity}. Lines up with how you already play: {labels}."
    return f"{identity}."


def _to_rec(
    player: PlaystyleVector,
    archetype: ChampionArchetype,
    fit_score: float,
    *,
    kind: Literal["comfort", "stretch"],
    stretch_axis: str | None,
) -> ChampionRec:
    matched = _matched_axes(player, archetype)
    return ChampionRec(
        champion=archetype.name,
        roles=list(archetype.roles),
        fit_score=round(fit_score, 4),
        kind=kind,
        matched_axes=matched,
        stretch_axis=stretch_axis,
        rationale=_rationale(archetype, matched_axes=matched, stretch_axis=stretch_axis),
    )


def recommend_champions(
    vector: PlaystyleVector,
    archetypes: list[ChampionArchetype],
    *,
    role: str | None = None,
    exclude: frozenset[str] = frozenset(),
    n_comfort: int = 3,
    n_stretch: int = 2,
) -> list[ChampionRec]:
    """Comfort picks are the top `n_comfort` archetypes by salience-weighted
    cosine similarity to the player's vector -- champions whose whole
    identity (not just a coincidental single axis) matches how the player
    already plays.

    Stretch picks are a deliberate second pass, not "ranks n_comfort+1..
    n_comfort+n_stretch by the same score". For every candidate NOT already
    picked as a comfort pick:

      1. find its single "weakest-fit" axis: the axis where it diverges
         most from the player, weighted by how much that axis defines the
         champion's identity (its own `salience`) -- see `_weakest_axis`;
      2. recompute the cosine fit with THAT axis excluded (`fit_excluding`);
      3. rank candidates by `fit_excluding` descending.

    A high `fit_excluding` means "if you set aside this one axis, this
    champion's identity looks just like yours" -- which is exactly the
    growth-suggestion framing a stretch pick should have: close enough to be
    achievable, off on one specific, nameable trait. `stretch_axis` on the
    returned rec is that excluded axis, so the API/UI can say what would be
    unfamiliar rather than just "this one's different."
    """
    candidates = [a for a in archetypes if a.name not in exclude]
    if role is not None:
        candidates = [a for a in candidates if role in a.roles]

    scored = sorted(((a, _weighted_cosine(vector, a)) for a in candidates), key=lambda t: t[1], reverse=True)
    comfort_picks = scored[:n_comfort]
    comfort_names = {a.name for a, _ in comfort_picks}

    stretch_scored = []
    for archetype, fit_score in scored:
        if archetype.name in comfort_names:
            continue
        weakest_axis = _weakest_axis(vector, archetype)
        fit_excluding = _weighted_cosine(vector, archetype, skip_axis=weakest_axis)
        stretch_scored.append((archetype, fit_score, fit_excluding, weakest_axis))
    stretch_scored.sort(key=lambda t: t[2], reverse=True)
    stretch_picks = stretch_scored[:n_stretch]

    recs = [_to_rec(vector, a, fit, kind="comfort", stretch_axis=None) for a, fit in comfort_picks]
    recs.extend(
        _to_rec(vector, a, fit, kind="stretch", stretch_axis=axis) for a, fit, _fit_excluding, axis in stretch_picks
    )
    return recs
