"""Typed, defensive views over raw match-v5 JSON.

This module quarantines the match-level Riot API quirks so nothing
downstream (metrics, detectors, the LLM boundary) ever touches a raw dict:

  - gameDuration units: milliseconds pre-patch-11.20 (no gameEndTimestamp
    key), seconds from 11.20 onward (gameEndTimestamp present). Riot's own
    recommended sentinel for telling the two apart.
  - Lane-opponent matching uses `teamPosition` ONLY, never `individualPosition`
    or the legacy `lane`/`role` fields, which are noisy and inconsistent.
    `teamPosition` is "" on ARAM and heavy role-swap games.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal

from lolcoach.domain.challenges import Challenges


def normalize_duration_s(info: dict[str, Any]) -> float:
    duration = info["gameDuration"]
    return float(duration) if "gameEndTimestamp" in info else float(duration) / 1000.0


@dataclass(frozen=True, slots=True)
class ParticipantView:
    raw: dict[str, Any]

    @property
    def puuid(self) -> str:
        return self.raw["puuid"]

    @property
    def participant_id(self) -> int:
        return self.raw["participantId"]

    @property
    def team_id(self) -> int:
        return self.raw["teamId"]

    @property
    def team_position(self) -> str:
        return self.raw.get("teamPosition", "") or ""

    @property
    def champion_id(self) -> int:
        return self.raw["championId"]

    @property
    def champion_name(self) -> str:
        return self.raw.get("championName", "")

    @property
    def win(self) -> bool:
        return bool(self.raw["win"])

    @property
    def kills(self) -> int:
        return self.raw.get("kills", 0)

    @property
    def deaths(self) -> int:
        return self.raw.get("deaths", 0)

    @property
    def assists(self) -> int:
        return self.raw.get("assists", 0)

    @property
    def total_cs(self) -> int:
        return self.raw.get("totalMinionsKilled", 0) + self.raw.get("neutralMinionsKilled", 0)

    @property
    def gold_earned(self) -> int:
        return self.raw.get("goldEarned", 0)

    @property
    def vision_score(self) -> int:
        return self.raw.get("visionScore", 0)

    @property
    def wards_placed(self) -> int:
        return self.raw.get("wardsPlaced", 0)

    @property
    def wards_killed(self) -> int:
        return self.raw.get("wardsKilled", 0)

    @property
    def total_time_spent_dead_s(self) -> int:
        return self.raw.get("totalTimeSpentDead", 0)

    @property
    def total_damage_dealt_to_champions(self) -> int:
        return self.raw.get("totalDamageDealtToChampions", 0)

    @property
    def damage_dealt_to_objectives(self) -> int:
        return self.raw.get("damageDealtToObjectives", 0)

    @property
    def damage_dealt_to_buildings(self) -> int:
        return self.raw.get("damageDealtToBuildings", 0)

    @property
    def challenges(self) -> Challenges:
        return Challenges(self.raw.get("challenges"))


@dataclass(frozen=True, slots=True)
class MatchView:
    raw: dict[str, Any]

    @property
    def match_id(self) -> str:
        return self.raw["metadata"]["matchId"]

    @property
    def queue_id(self) -> int:
        return self.raw["info"]["queueId"]

    @property
    def game_version(self) -> str:
        return self.raw["info"]["gameVersion"]

    @property
    def map_id(self) -> int:
        return self.raw["info"]["mapId"]

    @property
    def duration_s(self) -> float:
        return normalize_duration_s(self.raw["info"])

    @property
    def participants(self) -> tuple[ParticipantView, ...]:
        return tuple(ParticipantView(p) for p in self.raw["info"]["participants"])

    def participant_by_puuid(self, puuid: str) -> ParticipantView:
        for p in self.participants:
            if p.puuid == puuid:
                return p
        raise KeyError(f"puuid {puuid} not present in match {self.match_id}")

    def peer_group(self, subject: ParticipantView) -> PeerGroup:
        return PeerGroup.build(self, subject)


@dataclass(frozen=True, slots=True)
class PeerComparison:
    metric_value: float | None
    peer_value: float | None
    delta: float | None
    rank_in_lobby: int | None


PeerKind = Literal["lane_opponent", "role_cohort"]

MetricFn = Callable[[ParticipantView], float | None]


class PeerGroup:
    """The core benchmarking primitive: compares the subject against the
    other 9 players in the SAME match, never against an external corpus.
    Matchmaking already MMR-matched them, so this is self-calibrating.
    """

    def __init__(
        self,
        subject: ParticipantView,
        lane_opponent: ParticipantView | None,
        role_cohort: tuple[ParticipantView, ...],
        all_players: tuple[ParticipantView, ...],
    ) -> None:
        self.subject = subject
        self.lane_opponent = lane_opponent
        self.role_cohort = role_cohort
        self.all_players = all_players

    @classmethod
    def build(cls, match: MatchView, subject: ParticipantView) -> PeerGroup:
        all_players = match.participants
        position = subject.team_position
        lane_opponent: ParticipantView | None = None
        role_cohort: list[ParticipantView] = []
        if position:
            for p in all_players:
                if p.puuid == subject.puuid:
                    continue
                if p.team_position == position:
                    role_cohort.append(p)
                    if p.team_id != subject.team_id:
                        lane_opponent = p
        return cls(subject, lane_opponent, tuple(role_cohort), all_players)

    def compare(
        self,
        fn: MetricFn,
        *,
        higher_is_better: bool,
        peer: PeerKind = "lane_opponent",
    ) -> PeerComparison:
        value = fn(self.subject)
        if value is None:
            return PeerComparison(None, None, None, None)

        peer_value = self._peer_value(fn, peer)
        delta = (value - peer_value) if peer_value is not None else None
        rank = self.rank_in_lobby(fn, higher_is_better=higher_is_better)
        return PeerComparison(value, peer_value, delta, rank)

    def _peer_value(self, fn: MetricFn, peer: PeerKind) -> float | None:
        if peer == "lane_opponent":
            return fn(self.lane_opponent) if self.lane_opponent is not None else None
        if peer == "role_cohort":
            values = [v for p in self.role_cohort if (v := fn(p)) is not None]
            return sum(values) / len(values) if values else None
        raise ValueError(f"unknown peer kind: {peer!r}")

    def rank_in_lobby(self, fn: MetricFn, *, higher_is_better: bool) -> int | None:
        pairs: list[tuple[ParticipantView, float]] = []
        for p in self.all_players:
            v = fn(p)
            if v is not None:
                pairs.append((p, v))
        if not pairs:
            return None
        pairs.sort(key=lambda pv: pv[1], reverse=higher_is_better)
        for rank, (p, _) in enumerate(pairs, start=1):
            if p.puuid == self.subject.puuid:
                return rank
        return None


def iter_role_pairs(match: MatchView) -> Iterable[tuple[ParticipantView, ParticipantView | None]]:
    """Yield (participant, lane_opponent) for every participant in the match."""
    for p in match.participants:
        yield p, match.peer_group(p).lane_opponent
