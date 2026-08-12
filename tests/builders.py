"""Fluent builders for constructing synthetic matches/timelines in detector
tests. Because detectors are pure sync functions of an AnalysisContext, these
let a test construct the EXACT boundary condition under study (e.g. gold
sits at 1399 for 3 frames -> CLEAN; 1401 -> a finding) without needing a real
fixture.
"""

from __future__ import annotations

from typing import Any, Self

from lolcoach.detectors.context import AnalysisContext
from lolcoach.domain.match import MatchView
from lolcoach.domain.timeline import TimelineIndex
from tests.unit.factories import POSITIONS, make_match, make_participant


class MatchBuilder:
    def __init__(self) -> None:
        self._match_id = "NA1_9999999999"
        self._queue_id = 420
        self._duration_s: float = 1800.0
        self._participants: list[dict[str, Any]] = []

    def match_id(self, value: str) -> Self:
        self._match_id = value
        return self

    def queue_id(self, value: int) -> Self:
        self._queue_id = value
        return self

    def duration_minutes(self, minutes: float) -> Self:
        self._duration_s = minutes * 60.0
        return self

    def with_full_lobby(self, **subject_overrides: Any) -> Self:
        """10 participants, standard 5 positions per team. `subject_overrides`
        (raw or friendly key names, see `_translate_kwargs`) are applied to
        participant 1 (team 100, TOP) after construction.
        """
        self._participants = []
        for team_id in (100, 200):
            for i, position in enumerate(POSITIONS):
                pid = (0 if team_id == 100 else 5) + i + 1
                p = make_participant(pid, team_id=team_id, team_position=position, win=team_id == 100)
                if team_id == 100 and position == "TOP":
                    p.update(_translate_kwargs(subject_overrides))
                self._participants.append(p)
        return self

    def participant(self, participant_id: int, **kwargs: Any) -> Self:
        for p in self._participants:
            if p["participantId"] == participant_id:
                p.update(_translate_kwargs(kwargs))
                return self
        raise KeyError(f"no participant with id {participant_id}; call with_full_lobby() first")

    def build(self) -> MatchView:
        raw = make_match(
            match_id=self._match_id,
            queue_id=self._queue_id,
            game_duration=self._duration_s,
            participants=self._participants,
        )
        return MatchView(raw)


def _translate_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "total_time_spent_dead": "totalTimeSpentDead",
        "team_position": "teamPosition",
    }
    return {mapping.get(k, k): v for k, v in kwargs.items()}


class TimelineBuilder:
    def __init__(self, participants: int = 10) -> None:
        self._participants = list(range(1, participants + 1))
        self._frame_interval_ms = 60_000
        self._frames: dict[int, dict[str, Any]] = {}  # timestamp_ms -> frame dict
        self._events: list[dict[str, Any]] = []

    def frames(
        self,
        minutes: int,
        *,
        gold: dict[int, Any] | None = None,
        level: dict[int, Any] | None = None,
        position: dict[int, Any] | None = None,
    ) -> Self:
        """Populate one frame per minute from 0..minutes inclusive.

        `gold`/`level`/`position` map participant_id -> either a constant or
        a callable(minute) -> value, so a test can express e.g.
        `gold={1: lambda t: 1500 if t >= 12 else 400}`.
        """
        gold = gold or {}
        level = level or {}
        position = position or {}
        for minute in range(minutes + 1):
            ts_ms = minute * self._frame_interval_ms
            pframes = {}
            for pid in self._participants:
                g = _resolve(gold.get(pid), minute, default=1000)
                lvl = _resolve(level.get(pid), minute, default=min(1 + minute // 2, 18))
                pos = _resolve(position.get(pid), minute, default=None)
                pframes[str(pid)] = {
                    "participantId": pid,
                    "level": lvl,
                    "currentGold": g,
                    "totalGold": g,
                    "xp": 0,
                    "minionsKilled": 0,
                    "jungleMinionsKilled": 0,
                }
                if pos is not None:
                    pframes[str(pid)]["position"] = {"x": pos[0], "y": pos[1]}
            self._frames[ts_ms] = {"timestamp": ts_ms, "participantFrames": pframes, "events": []}
        return self

    def kill(
        self,
        *,
        t_s: float,
        killer: int,
        victim: int,
        assists: list[int] | None = None,
        pos: tuple[int, int] | None = None,
    ) -> Self:
        event: dict[str, Any] = {
            "type": "CHAMPION_KILL",
            "timestamp": int(t_s * 1000),
            "killerId": killer,
            "victimId": victim,
            "assistingParticipantIds": assists or [],
        }
        if pos is not None:
            event["position"] = {"x": pos[0], "y": pos[1]}
        self._events.append(event)
        return self

    def elite_monster(self, *, t_s: float, team: int, monster: str) -> Self:
        self._events.append(
            {
                "type": "ELITE_MONSTER_KILL",
                "timestamp": int(t_s * 1000),
                "killerTeamId": team,
                "monsterType": monster,
            }
        )
        return self

    def ward_placed(self, *, t_s: float, creator: int, ward_type: str = "YELLOW_TRINKET") -> Self:
        self._events.append(
            {"type": "WARD_PLACED", "timestamp": int(t_s * 1000), "creatorId": creator, "wardType": ward_type}
        )
        return self

    def level_up(self, *, t_s: float, participant: int, level: int) -> Self:
        self._events.append(
            {"type": "LEVEL_UP", "timestamp": int(t_s * 1000), "participantId": participant, "level": level}
        )
        return self

    def build(self) -> TimelineIndex:
        # Each frame captures events in [this frame's timestamp, next frame's
        # timestamp); the last frame captures everything from its timestamp
        # onward, so an event at/after the last requested minute is never
        # silently dropped.
        sorted_ts = sorted(self._frames)
        frames = []
        for i, ts_ms in enumerate(sorted_ts):
            frame = self._frames[ts_ms]
            next_ts = sorted_ts[i + 1] if i + 1 < len(sorted_ts) else None
            if next_ts is None:
                frame_events = [e for e in self._events if e["timestamp"] >= ts_ms]
            else:
                frame_events = [e for e in self._events if ts_ms <= e["timestamp"] < next_ts]
            frames.append({**frame, "events": frame_events})
        raw = {"info": {"frameInterval": self._frame_interval_ms, "frames": frames}}
        return TimelineIndex(raw)


def _resolve(spec: Any, minute: int, *, default: Any) -> Any:
    if spec is None:
        return default
    if callable(spec):
        return spec(minute)
    return spec


def make_context(
    match: MatchView, timeline: TimelineIndex | None, subject_puuid: str = "PUUID_01"
) -> AnalysisContext:
    return AnalysisContext.build(match, timeline, subject_puuid)
