"""Builds a PlaystyleVector from already-loaded MatchView objects.

This is the domain-facing half of the playstyle split (see vector.py's
module docstring for why the schema and the builder live in separate
modules, mirroring analysis/build.py vs analysis/factsheet.py). Pure
computation -- no I/O, no Riot client, no FastAPI. Callers (service.py) are
responsible for loading match JSON from the cache first.

## The percentile principle

Every axis is the MEAN, across the player's recent games, of that game's
LOBBY PERCENTILE RANK on 2-3 contributing metrics -- the same peer-relative
principle as `PeerGroup.rank_in_lobby` (domain/match.py): a metric is only
ever compared to the *other players in that one match*, never to an
absolute threshold or to players outside the lobby.

`PeerGroup.rank_in_lobby` itself assumes a fixed lobby of ~10, so this
module reimplements the same ranking logic against the ACTUAL number of
players in a match who have a value for that metric (Arena lobbies in this
codebase's real cached data have 16-18 participants, not 10, and any
individual metric may be present for fewer than the full lobby). Rank 1
(best) -> score 1.0, rank N (worst) -> score 0.0, linear in between --
`percentile_rank_score` below generalizes the task's documented boundary
example, `(10 - rank) / 9`, to `(n - rank) / (n - 1)` for a lobby of n.

A metric whose source field is absent for a game (`Challenges.get` returning
None, or fewer than 2 players in the lobby having a value at all) is
skipped for that game -- never treated as 0. An axis whose every
contributing metric is unavailable for a game skips that game entirely.

## Confidence

`sample_size` counts games that contributed to at least one axis.
`confidence` combines two factors, both simple and documented rather than
statistically rigorous (this is a UX signal, not a p-value):

  - a size factor that ramps 0 -> 1 as sample_size goes 0 -> 10 games
    (linear, capped at 1.0 -- more than 10 games doesn't add confidence);
  - a variance penalty: the average per-axis population stdev of the
    per-game scores (each already in [0, 1], so stdev is naturally bounded),
    subtracted from 1.0 -- consistent play (low stdev) keeps the penalty
    near 1.0, wildly swingy play pulls it down.

The two factors are multiplied and clamped to [0, 1].
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence

from lolcoach.domain.match import MatchView, ParticipantView, PeerGroup
from lolcoach.metrics.combat import deaths_per_minute, time_dead_share
from lolcoach.metrics.economy import cs_per_minute
from lolcoach.playstyle.vector import AXES, PlaystyleVector

MetricFn = Callable[[ParticipantView], float | None]
# (metric fn, whether a HIGHER raw value maps to a HIGHER axis score --
# purely a ranking direction for the trait being measured, not a judgement
# of "good"/"bad" play, e.g. more time spent dead maps to MORE risk_tolerance).
AxisMetric = tuple[MetricFn, bool]


def percentile_rank_score(rank: int, lobby_size: int) -> float:
    """Convert a 1-indexed lobby rank (1 = best) into a 0..1 score.

    rank=1 in a lobby of `lobby_size` -> 1.0 ("better than everyone else").
    rank=lobby_size -> 0.0 ("worse than everyone else"). Requires
    lobby_size >= 2 (a percentile against a lobby of one is meaningless).
    """
    if lobby_size < 2:
        raise ValueError("need at least 2 players with a value to compute a percentile")
    return (lobby_size - rank) / (lobby_size - 1)


def _axis_score_for_game(peer_group: PeerGroup, metrics: Sequence[AxisMetric]) -> float | None:
    """Mean percentile score across whichever of `metrics` have a value for
    the subject AND at least one other player in this match. None if none
    of the metrics are available for this game.
    """
    per_metric_scores: list[float] = []
    for fn, higher_is_more in metrics:
        subject_value = fn(peer_group.subject)
        if subject_value is None:
            continue
        pairs = [(p, v) for p in peer_group.all_players if (v := fn(p)) is not None]
        if len(pairs) < 2:
            continue
        pairs.sort(key=lambda pv: pv[1], reverse=higher_is_more)
        rank = next((i for i, (p, _v) in enumerate(pairs, start=1) if p.puuid == peer_group.subject.puuid), None)
        if rank is None:
            continue
        per_metric_scores.append(percentile_rank_score(rank, len(pairs)))
    if not per_metric_scores:
        return None
    return sum(per_metric_scores) / len(per_metric_scores)


def _aggression_metrics(duration_s: float) -> list[AxisMetric]:
    return [
        (lambda p: p.challenges.get("killParticipation"), True),
        (lambda p: p.challenges.get("soloKills"), True),
        (lambda p: p.challenges.get("teamDamagePercentage"), True),
    ]


def _farming_metrics(duration_s: float) -> list[AxisMetric]:
    return [
        (lambda p: cs_per_minute(p, duration_s), True),
        (lambda p: p.challenges.get("laneMinionsFirst10Minutes"), True),
    ]


def _vision_metrics(duration_s: float) -> list[AxisMetric]:
    def vision_score_per_minute(p: ParticipantView) -> float | None:
        value = p.challenges.get("visionScorePerMinute")
        if value is not None:
            return value
        if duration_s <= 0:
            return None
        return p.vision_score / (duration_s / 60.0)

    return [
        (vision_score_per_minute, True),
        (lambda p: float(p.wards_placed), True),
        (lambda p: float(p.wards_killed), True),
    ]


def _objective_metrics(duration_s: float) -> list[AxisMetric]:
    def epic_takedowns(p: ParticipantView) -> float:
        # Deliberately `.get(key, 0)`, not the usual "absent -> skip": the
        # task spec calls for missing takedown counters to read as 0 (a
        # player who genuinely got 0 dragon/baron/herald takedowns is
        # indistinguishable from a field the API omitted for being 0).
        return (
            (p.challenges.get("dragonTakedowns", 0) or 0)
            + (p.challenges.get("baronTakedowns", 0) or 0)
            + (p.challenges.get("riftHeraldTakedowns", 0) or 0)
        )

    return [
        (epic_takedowns, True),
        (lambda p: float(p.damage_dealt_to_objectives), True),
    ]


def _risk_metrics(duration_s: float) -> list[AxisMetric]:
    def dpm(p: ParticipantView) -> float | None:
        if duration_s <= 0:
            return None
        return deaths_per_minute(p.deaths, duration_s)

    return [
        (lambda p: time_dead_share(p.total_time_spent_dead_s, duration_s), True),
        (dpm, True),
    ]


def _teamfight_metrics(duration_s: float) -> list[AxisMetric]:
    # Weakest axis by design (see build.py's docstring / the task's own
    # note): `multikills` is the closest real signal to "fights alongside
    # the team", weighed against `damageDealtToBuildings` (a splitpush
    # signal, so its ranking direction is INVERTED -- more building damage
    # relative to the lobby pulls the axis toward split-push, not away).
    # Both fields are confirmed present in this codebase's real cached
    # match JSON (see the M7 smoke test) -- `multikills` under `challenges`,
    # `damageDealtToBuildings` as a top-level participant field.
    return [
        (lambda p: p.challenges.get("multikills"), True),
        (lambda p: float(p.damage_dealt_to_buildings), False),
    ]


_AXIS_METRIC_BUILDERS: dict[str, Callable[[float], list[AxisMetric]]] = {
    "aggression": _aggression_metrics,
    "farming": _farming_metrics,
    "vision": _vision_metrics,
    "objective_focus": _objective_metrics,
    "risk_tolerance": _risk_metrics,
    "teamfight_vs_split": _teamfight_metrics,
}

# Neutral fallback for an axis with zero contributing games across the
# whole sample -- avoids biasing recommendations toward either extreme.
_NEUTRAL_AXIS_SCORE = 0.5


def build_playstyle_vector(matches: Sequence[tuple[MatchView, str]]) -> PlaystyleVector:
    """`matches` is (MatchView, subject_puuid) pairs. In practice callers pass
    the same puuid for every match (one player's indexed history), but
    keeping it per-tuple means the caller doesn't need a separate "does this
    match contain this puuid" check -- a match missing the puuid is just
    skipped below.
    """
    axis_game_scores: dict[str, list[float]] = {axis: [] for axis in AXES}
    contributing_match_ids: set[str] = set()

    for match, puuid in matches:
        try:
            subject = match.participant_by_puuid(puuid)
        except KeyError:
            continue
        peer_group = match.peer_group(subject)
        duration_s = match.duration_s

        contributed = False
        for axis, builder in _AXIS_METRIC_BUILDERS.items():
            score = _axis_score_for_game(peer_group, builder(duration_s))
            if score is not None:
                axis_game_scores[axis].append(score)
                contributed = True
        if contributed:
            contributing_match_ids.add(match.match_id)

    axis_values = {
        axis: (sum(scores) / len(scores) if scores else _NEUTRAL_AXIS_SCORE)
        for axis, scores in axis_game_scores.items()
    }
    sample_size = len(contributing_match_ids)
    confidence = _confidence(axis_game_scores, sample_size)

    return PlaystyleVector(
        **axis_values,
        sample_size=sample_size,
        confidence=confidence,
    )


def _confidence(axis_game_scores: dict[str, list[float]], sample_size: int) -> float:
    size_factor = min(1.0, sample_size / 10.0)

    stdevs = [statistics.pstdev(scores) for scores in axis_game_scores.values() if len(scores) >= 2]
    variance_penalty = 1.0 - (sum(stdevs) / len(stdevs)) if stdevs else 1.0

    return max(0.0, min(1.0, size_factor * variance_penalty))
