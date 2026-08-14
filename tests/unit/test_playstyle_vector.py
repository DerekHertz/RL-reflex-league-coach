from __future__ import annotations

import pytest

from lolcoach.playstyle.build import build_playstyle_vector, percentile_rank_score
from tests.builders import MatchBuilder

_HIGH_AGGRESSION = {"killParticipation": 0.9, "soloKills": 5, "teamDamagePercentage": 0.5}
_LOW_AGGRESSION = {"killParticipation": 0.1, "soloKills": 0, "teamDamagePercentage": 0.05}


def _match_with_challenges(match_id: str, subject_challenges: dict, other_challenges: dict):
    builder = MatchBuilder().match_id(match_id).with_full_lobby(challenges=subject_challenges)
    for pid in range(2, 11):
        builder.participant(pid, challenges=other_challenges)
    return builder.build()


def test_percentile_rank_score_boundary_values() -> None:
    # rank 1/10 (best) -> highest score; rank 10/10 (worst) -> lowest score.
    assert percentile_rank_score(1, 10) == 1.0
    assert percentile_rank_score(10, 10) == 0.0
    # Generalizes beyond a 10-player lobby (real cached Arena matches have
    # 16-18 participants).
    assert percentile_rank_score(1, 18) == 1.0
    assert percentile_rank_score(18, 18) == 0.0
    # Midpoint of a 2-player comparison.
    assert percentile_rank_score(1, 2) == 1.0
    assert percentile_rank_score(2, 2) == 0.0


def test_percentile_rank_score_requires_at_least_two_players() -> None:
    with pytest.raises(ValueError):
        percentile_rank_score(1, 1)


def test_aggression_axis_reaches_max_score_when_subject_dominates_every_metric() -> None:
    match = _match_with_challenges("NA1_AGG_HIGH", _HIGH_AGGRESSION, _LOW_AGGRESSION)
    vector = build_playstyle_vector([(match, "PUUID_01")])
    assert vector.aggression == pytest.approx(1.0)
    assert vector.sample_size == 1


def test_aggression_axis_reaches_min_score_when_subject_trails_every_metric() -> None:
    match = _match_with_challenges("NA1_AGG_LOW", _LOW_AGGRESSION, _HIGH_AGGRESSION)
    vector = build_playstyle_vector([(match, "PUUID_01")])
    assert vector.aggression == pytest.approx(0.0)


def test_missing_challenges_blob_does_not_crash_and_is_excluded_from_axis_average() -> None:
    # Game 1: subject dominates aggression's 3 challenges-only metrics ->
    # that game's aggression score is 1.0.
    game1 = _match_with_challenges("NA1_MISSING_1", _HIGH_AGGRESSION, _LOW_AGGRESSION)

    # Game 2: `challenges` is present-but-empty for EVERY participant (the
    # ARAM/old-patch/Arena case) -- aggression's 3 source fields are all
    # absent, so the whole aggression axis must be skipped for this game,
    # not crash and not silently score as 0.
    builder2 = MatchBuilder().match_id("NA1_MISSING_2").with_full_lobby(challenges={})
    for pid in range(2, 11):
        builder2.participant(pid, challenges={})
    game2 = builder2.build()

    vector = build_playstyle_vector([(game1, "PUUID_01"), (game2, "PUUID_01")])

    # Only game1 contributed to aggression, so the average is exactly
    # game1's score (1.0), not diluted by a phantom 0 from game2.
    assert vector.aggression == pytest.approx(1.0)
    # Game2 still contributes to `sample_size` via axes with raw-field
    # (non-challenges) metrics, e.g. farming's cs_per_minute -- it isn't
    # dropped from the sample entirely, just from the aggression axis.
    assert vector.sample_size == 2


def test_sample_size_and_confidence_scale_with_games_and_variance() -> None:
    one_game = [(_match_with_challenges("NA1_ONE", _HIGH_AGGRESSION, _LOW_AGGRESSION), "PUUID_01")]
    vector_one = build_playstyle_vector(one_game)

    consistent_games = [
        (_match_with_challenges(f"NA1_CONSISTENT_{i}", _HIGH_AGGRESSION, _LOW_AGGRESSION), "PUUID_01")
        for i in range(10)
    ]
    vector_consistent = build_playstyle_vector(consistent_games)

    varying_games = [
        (
            _match_with_challenges(
                f"NA1_VARYING_{i}",
                _HIGH_AGGRESSION if i % 2 == 0 else _LOW_AGGRESSION,
                _LOW_AGGRESSION if i % 2 == 0 else _HIGH_AGGRESSION,
            ),
            "PUUID_01",
        )
        for i in range(10)
    ]
    vector_varying = build_playstyle_vector(varying_games)

    assert vector_one.sample_size == 1
    assert vector_consistent.sample_size == 10
    assert vector_varying.sample_size == 10

    # More games and lower variance both raise confidence.
    assert vector_one.confidence < vector_consistent.confidence
    assert vector_varying.confidence < vector_consistent.confidence
    for v in (vector_one, vector_consistent, vector_varying):
        assert 0.0 <= v.confidence <= 1.0


def test_build_playstyle_vector_skips_matches_missing_the_subject_puuid() -> None:
    match = _match_with_challenges("NA1_NOSUBJECT", _HIGH_AGGRESSION, _LOW_AGGRESSION)
    vector = build_playstyle_vector([(match, "PUUID_DOES_NOT_EXIST")])
    assert vector.sample_size == 0
    # Neutral fallback, not a crash or a biased default.
    assert vector.aggression == 0.5
