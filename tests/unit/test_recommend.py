"""recommend_champions tests. The arrange sections hand-compute the expected
weighted cosine similarities so the assertions aren't just "the code agrees
with itself" -- see each test's comment block for the arithmetic.
"""

from __future__ import annotations

import math

import pytest

from lolcoach.playstyle.archetypes import ChampionArchetype
from lolcoach.playstyle.recommend import recommend_champions
from lolcoach.playstyle.vector import PlaystyleVector

_ZERO_AXES = {
    "aggression": 0.0,
    "farming": 0.0,
    "vision": 0.0,
    "objective_focus": 0.0,
    "risk_tolerance": 0.0,
    "teamfight_vs_split": 0.0,
}
_ZERO_SALIENCE = dict(_ZERO_AXES)


def _archetype(name: str, roles: list[str], axes: dict, salience: dict) -> ChampionArchetype:
    return ChampionArchetype.model_validate(
        {"name": name, "roles": roles, "axes": axes, "salience": salience, "identity": f"{name} test identity"}
    )


def test_weighted_cosine_ranking_matches_hand_computation() -> None:
    # Player vector points purely along the aggression axis (1.0), with 0 on
    # every other axis. Only aggression and teamfight_vs_split carry any
    # salience for the 3 archetypes below, so this reduces to 2D cosine
    # similarity that's easy to verify by hand:
    #   Aligned:      (1, 0) vs (1, 0) -> cos 0deg  = 1.0
    #   Diagonal:     (1, 0) vs (1, 1) -> cos 45deg = 1/sqrt(2) ~= 0.7071
    #   Perpendicular:(1, 0) vs (0, 1) -> cos 90deg = 0.0
    player = PlaystyleVector(
        aggression=1.0, farming=0.0, vision=0.0, objective_focus=0.0, risk_tolerance=0.0, teamfight_vs_split=0.0,
        sample_size=10, confidence=0.9,
    )
    salience = {**_ZERO_SALIENCE, "aggression": 1.0, "teamfight_vs_split": 1.0}
    aligned = _archetype("Aligned", ["MIDDLE"], {**_ZERO_AXES, "aggression": 1.0, "teamfight_vs_split": 0.0}, salience)
    diagonal = _archetype("Diagonal", ["MIDDLE"], {**_ZERO_AXES, "aggression": 1.0, "teamfight_vs_split": 1.0}, salience)
    perpendicular = _archetype("Perpendicular", ["MIDDLE"], {**_ZERO_AXES, "aggression": 0.0, "teamfight_vs_split": 1.0}, salience)

    recs = recommend_champions(player, [perpendicular, diagonal, aligned], n_comfort=3, n_stretch=0)

    assert [r.champion for r in recs] == ["Aligned", "Diagonal", "Perpendicular"]
    assert recs[0].fit_score == pytest.approx(1.0, abs=1e-6)
    assert recs[1].fit_score == pytest.approx(1.0 / math.sqrt(2), abs=1e-4)
    assert recs[2].fit_score == pytest.approx(0.0, abs=1e-6)
    assert all(r.kind == "comfort" for r in recs)


def test_role_filter_excludes_out_of_role_champions() -> None:
    player = PlaystyleVector(
        aggression=0.7, farming=0.5, vision=0.3, objective_focus=0.4, risk_tolerance=0.5, teamfight_vs_split=0.5,
        sample_size=5, confidence=0.5,
    )
    uniform_salience = {axis: 1.0 for axis in _ZERO_SALIENCE}
    top_champ = _archetype("TopChamp", ["TOP"], {**_ZERO_AXES, "aggression": 0.7, "farming": 0.5, "vision": 0.3, "objective_focus": 0.4, "risk_tolerance": 0.5, "teamfight_vs_split": 0.5}, uniform_salience)
    jungle_champ = _archetype("JungleChamp", ["JUNGLE"], {**_ZERO_AXES, "aggression": 0.7, "farming": 0.5, "vision": 0.3, "objective_focus": 0.4, "risk_tolerance": 0.5, "teamfight_vs_split": 0.5}, uniform_salience)

    recs = recommend_champions(player, [top_champ, jungle_champ], role="TOP", n_comfort=3, n_stretch=0)

    assert [r.champion for r in recs] == ["TopChamp"]
    assert all("TOP" in r.roles for r in recs)


def test_comfort_and_stretch_picks_are_distinct_and_stretch_diverges_on_claimed_axis() -> None:
    # Player vector with all 6 axes distinct so cross-axis divergence is
    # unambiguous.
    player = PlaystyleVector(
        aggression=0.8, farming=0.5, vision=0.2, objective_focus=0.3, risk_tolerance=0.6, teamfight_vs_split=0.4,
        sample_size=8, confidence=0.7,
    )
    uniform_salience = {axis: 1.0 for axis in _ZERO_SALIENCE}

    # Identical to the player on every axis -> fit == 1.0 exactly.
    close_match = _archetype(
        "CloseMatch", ["MIDDLE"],
        {"aggression": 0.8, "farming": 0.5, "vision": 0.2, "objective_focus": 0.3, "risk_tolerance": 0.6, "teamfight_vs_split": 0.4},
        uniform_salience,
    )
    # Identical to the player on 5 axes, wildly different on vision (0.2 ->
    # 0.9). Hand-computed (weighted cosine, all weights 1.0):
    #   numerator = 0.64 + 0.25 + 0.18 + 0.09 + 0.36 + 0.16 = 1.68
    #   |player|^2 = 0.64 + 0.25 + 0.04 + 0.09 + 0.36 + 0.16 = 1.54
    #   |champ|^2  = 0.64 + 0.25 + 0.81 + 0.09 + 0.36 + 0.16 = 2.31
    #   fit = 1.68 / (sqrt(1.54) * sqrt(2.31)) ~= 0.8908
    # Excluding the vision axis (its single largest weighted divergence),
    # the remaining 5 axes are IDENTICAL to the player -> fit_excluding = 1.0.
    mostly_match_but_vision = _archetype(
        "MostlyMatchButVision", ["MIDDLE"],
        {"aggression": 0.8, "farming": 0.5, "vision": 0.9, "objective_focus": 0.3, "risk_tolerance": 0.6, "teamfight_vs_split": 0.4},
        uniform_salience,
    )
    # Diverges heavily on most axes -> low fit and a poor fit_excluding too,
    # so it should be picked as neither comfort nor stretch.
    poor_fit = _archetype(
        "PoorFit", ["MIDDLE"],
        {"aggression": 0.1, "farming": 0.1, "vision": 0.1, "objective_focus": 0.9, "risk_tolerance": 0.1, "teamfight_vs_split": 0.9},
        uniform_salience,
    )

    recs = recommend_champions(
        player, [close_match, mostly_match_but_vision, poor_fit], n_comfort=1, n_stretch=1
    )

    assert len(recs) == 2
    comfort = [r for r in recs if r.kind == "comfort"]
    stretch = [r for r in recs if r.kind == "stretch"]
    assert [r.champion for r in comfort] == ["CloseMatch"]
    assert [r.champion for r in stretch] == ["MostlyMatchButVision"]

    comfort_rec = comfort[0]
    stretch_rec = stretch[0]
    assert comfort_rec.fit_score == pytest.approx(1.0, abs=1e-6)
    assert comfort_rec.stretch_axis is None
    assert stretch_rec.fit_score == pytest.approx(0.8908, abs=1e-3)
    assert stretch_rec.stretch_axis == "vision"
    # The stretch pick is close to the player everywhere EXCEPT the claimed
    # divergence axis -- vision must not show up as a "matched" axis.
    assert "vision" not in stretch_rec.matched_axes

    # Comfort and stretch picks are a disjoint set of champions.
    assert {r.champion for r in comfort} & {r.champion for r in stretch} == set()

    # PoorFit isn't good enough for either bucket.
    assert "PoorFit" not in {r.champion for r in recs}
