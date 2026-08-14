from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lolcoach.domain.geometry import (
    MAP_CENTER,
    MAP_MAX,
    MAP_MIN,
    Landmark,
    MapGeometry,
    map_depth,
    side_normalize,
    to_unit_square,
)

# A geometry instance with the real, empirically-derived landmarks (from
# data/map_landmarks.json via scripts/derive_landmarks.py), loaded once so
# tests exercise the actual centroids the app ships with.
_GEO = MapGeometry.load()


# ---------------------------------------------------------------------------
# side_normalize
# ---------------------------------------------------------------------------


def test_side_normalize_blue_is_identity() -> None:
    assert side_normalize(1234.0, 5678.0, 100) == (1234.0, 5678.0)


def test_side_normalize_red_mirrors_through_center() -> None:
    x, y = side_normalize(1234.0, 5678.0, 200)
    assert x == 2 * MAP_CENTER[0] - 1234.0
    assert y == 2 * MAP_CENTER[1] - 5678.0


@given(
    x=st.floats(min_value=MAP_MIN[0], max_value=MAP_MAX[0], allow_nan=False),
    y=st.floats(min_value=MAP_MIN[1], max_value=MAP_MAX[1], allow_nan=False),
)
def test_mirrored_point_classifies_to_same_region(x: float, y: float) -> None:
    """A point on blue's side of the map and its mirror-image on red's side
    (i.e. the same physical location, described from the other team's raw
    coordinate frame) must classify to the same region name once each is
    side-normalized from its own team's perspective. This is the whole point
    of side_normalize: region logic is written once, from blue's POV.
    """
    region_as_blue = _GEO.region_of(x, y, 100)

    # The point on the map that a red-team player's raw (x, y) would need to
    # be for it to describe this same blue-side location once mirrored.
    mirrored_x = 2 * MAP_CENTER[0] - x
    mirrored_y = 2 * MAP_CENTER[1] - y
    region_as_red = _GEO.region_of(mirrored_x, mirrored_y, 200)

    assert region_as_blue == region_as_red


# ---------------------------------------------------------------------------
# to_unit_square / map_depth
# ---------------------------------------------------------------------------


def test_unit_square_bounds_map_to_0_and_1() -> None:
    assert to_unit_square(*MAP_MIN) == (0.0, 0.0)
    assert to_unit_square(*MAP_MAX) == (1.0, 1.0)


def test_map_depth_zero_at_own_fountain_corner() -> None:
    u, v = to_unit_square(*MAP_MIN)
    assert map_depth(u, v) == 0.0


def test_map_depth_one_at_enemy_fountain_corner() -> None:
    u, v = to_unit_square(*MAP_MAX)
    assert map_depth(u, v) == 1.0


def test_map_depth_half_at_center() -> None:
    u, v = to_unit_square(*MAP_CENTER)
    assert abs(map_depth(u, v) - 0.5) < 1e-6


# ---------------------------------------------------------------------------
# MapGeometry.region_of -- known-good synthetic coordinates per region
# ---------------------------------------------------------------------------

# Hand-picked from a fine-grained scan of the actual classifier so each point
# sits comfortably inside its region, away from band edges.
_REGION_POINTS: dict[str, tuple[float, float]] = {
    "own_fountain": (555, 1314),
    "enemy_fountain": (14195, 13848),
    "mid_lane": (7375, 7883),
    "top_lane": (2503, 14829),
    "bot_lane": (12247, 4712),
    "river": (7375, 5618),
    "own_top_jungle": (2128, 7808),
    "own_bot_jungle": (6251, 2145),
    "enemy_top_jungle": (8499, 12262),
    "enemy_bot_jungle": (12622, 6826),
    "baron_pit": (4902, 9318),
    "dragon_pit": (9923, 3580),
}


def test_region_points_cover_every_named_region() -> None:
    expected = {
        "own_fountain",
        "enemy_fountain",
        "mid_lane",
        "top_lane",
        "bot_lane",
        "river",
        "own_top_jungle",
        "own_bot_jungle",
        "enemy_top_jungle",
        "enemy_bot_jungle",
        "baron_pit",
        "dragon_pit",
    }
    assert set(_REGION_POINTS) == expected


def test_region_of_known_good_coordinates() -> None:
    for expected_region, (x, y) in _REGION_POINTS.items():
        assert _GEO.region_of(x, y, 100) == expected_region, f"{expected_region} @ ({x}, {y})"


def test_region_of_exact_landmark_centroids() -> None:
    assert _GEO.region_of(*_GEO.baron_pit.centroid, 100) == "baron_pit"
    assert _GEO.region_of(*_GEO.dragon_pit.centroid, 100) == "dragon_pit"


def test_region_of_is_team_relative_not_side_absolute() -> None:
    """The same raw coordinate should generally classify differently for
    blue vs red, because "own"/"enemy" are relative to team_id."""
    x, y = _REGION_POINTS["own_fountain"]
    assert _GEO.region_of(x, y, 100) == "own_fountain"
    assert _GEO.region_of(x, y, 200) == "enemy_fountain"


def test_map_geometry_load_reads_real_derived_landmarks() -> None:
    geo = MapGeometry.load()
    assert geo.baron_pit.sample_count >= 3
    assert geo.dragon_pit.sample_count >= 3


def test_pit_radius_can_be_overridden_for_synthetic_landmarks() -> None:
    geo = MapGeometry(
        baron_pit=Landmark("baron_pit", (5000.0, 10000.0), 10),
        dragon_pit=Landmark("dragon_pit", (10000.0, 5000.0), 10),
        pit_radius=100.0,
    )
    assert geo.region_of(5000, 10000, 100) == "baron_pit"
    assert geo.region_of(5000 + 500, 10000, 100) != "baron_pit"
