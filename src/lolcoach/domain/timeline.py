"""Typed, defensive views over match-v5 timeline JSON.

Quarantines the timeline-level Riot API quirks:

  - `participantFrames` is a dict keyed by the STRINGS "1".."10", not an
    array -- indexing it with an int silently KeyErrors.
  - `minionsKilled`/`jungleMinionsKilled`/`totalGold` are cumulative per
    frame, not deltas.
  - A live bug (since ~patch 15.17) emits exact-duplicate `SKILL_LEVEL_UP`
    events -- deduped here on (participantId, skillSlot, timestamp).
  - `frameInterval` is read from the response rather than hardcoded to
    60000ms, though that's the only observed value on Summoner's Rift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ParticipantFrame:
    raw: dict[str, Any]

    @property
    def participant_id(self) -> int:
        return self.raw["participantId"]

    @property
    def level(self) -> int:
        return self.raw["level"]

    @property
    def current_gold(self) -> int:
        return self.raw["currentGold"]

    @property
    def total_gold(self) -> int:
        return self.raw["totalGold"]

    @property
    def xp(self) -> int:
        return self.raw["xp"]

    @property
    def minions_killed(self) -> int:
        return self.raw.get("minionsKilled", 0)

    @property
    def jungle_minions_killed(self) -> int:
        return self.raw.get("jungleMinionsKilled", 0)

    @property
    def cs(self) -> int:
        return self.minions_killed + self.jungle_minions_killed

    @property
    def position(self) -> tuple[int, int] | None:
        pos = self.raw.get("position")
        if not pos:
            return None
        return (pos["x"], pos["y"])


@dataclass(frozen=True, slots=True)
class Frame:
    raw: dict[str, Any]

    @property
    def timestamp_ms(self) -> int:
        return self.raw["timestamp"]

    @property
    def timestamp_s(self) -> float:
        return self.timestamp_ms / 1000.0

    @property
    def events(self) -> list[dict[str, Any]]:
        return self.raw.get("events", [])

    def participant_frame(self, participant_id: int) -> ParticipantFrame:
        return ParticipantFrame(self.raw["participantFrames"][str(participant_id)])

    def all_participant_frames(self) -> dict[int, ParticipantFrame]:
        return {int(pid): ParticipantFrame(pf) for pid, pf in self.raw["participantFrames"].items()}


class TimelineIndex:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self._frames: tuple[Frame, ...] = tuple(Frame(f) for f in raw["info"]["frames"])
        self._events: tuple[dict[str, Any], ...] = tuple(self._flatten_and_dedupe_events())

    @property
    def frame_interval_ms(self) -> int:
        return self._raw["info"]["frameInterval"]

    @property
    def frames(self) -> tuple[Frame, ...]:
        return self._frames

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        """All events across the game, flattened and time-sorted."""
        return self._events

    def _flatten_and_dedupe_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        seen_skill_ups: set[tuple[Any, Any, Any]] = set()
        for frame in self._frames:
            for event in frame.events:
                if event.get("type") == "SKILL_LEVEL_UP":
                    key = (event.get("participantId"), event.get("skillSlot"), event.get("timestamp"))
                    if key in seen_skill_ups:
                        continue
                    seen_skill_ups.add(key)
                events.append(event)
        events.sort(key=lambda e: e["timestamp"])
        return events

    def events_of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [e for e in self._events if e.get("type") == event_type]

    def participant_frame_series(self, participant_id: int) -> list[ParticipantFrame]:
        return [f.participant_frame(participant_id) for f in self._frames]

    def frame_at_or_before(self, timestamp_ms: int) -> Frame | None:
        """The last frame whose timestamp is <= timestamp_ms, or None if the
        game hadn't reached its first frame yet.
        """
        candidate: Frame | None = None
        for f in self._frames:
            if f.timestamp_ms <= timestamp_ms:
                candidate = f
            else:
                break
        return candidate

    def level_at(self, participant_id: int, timestamp_ms: int) -> int | None:
        """The participant's level at a given moment, derived from LEVEL_UP
        events rather than frame sampling (frames are once-per-minute; level
        matters exactly, e.g. for death-timer computation).
        """
        level = 1
        found = False
        for event in self.events_of_type("LEVEL_UP"):
            if event.get("participantId") != participant_id:
                continue
            if event["timestamp"] > timestamp_ms:
                break
            level = event["level"]
            found = True
        if not found:
            frame = self.frame_at_or_before(timestamp_ms)
            if frame is not None:
                return frame.participant_frame(participant_id).level
        return level
