"""Minimal, hand-built match/timeline dict factories for unit tests.

Not the full scrubbed-fixture corpus (that's tests/fixtures/, built from real
matches in M2+) -- these are synthetic, deliberately small, and exist purely
to exercise domain-layer parsing logic.
"""

from __future__ import annotations

from typing import Any

POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def make_participant(
    participant_id: int,
    *,
    team_id: int,
    team_position: str,
    champion_name: str = "Ahri",
    champion_id: int = 103,
    win: bool = True,
    kills: int = 5,
    deaths: int = 3,
    assists: int = 4,
    total_minions_killed: int = 150,
    neutral_minions_killed: int = 0,
    gold_earned: int = 12000,
    vision_score: int = 20,
    puuid: str | None = None,
    challenges: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "puuid": puuid or f"PUUID_{participant_id:02d}",
        "participantId": participant_id,
        "teamId": team_id,
        "teamPosition": team_position,
        "championId": champion_id,
        "championName": champion_name,
        "win": win,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "totalMinionsKilled": total_minions_killed,
        "neutralMinionsKilled": neutral_minions_killed,
        "goldEarned": gold_earned,
        "visionScore": vision_score,
        "wardsPlaced": 8,
        "wardsKilled": 1,
        "totalTimeSpentDead": 60,
        "totalDamageDealtToChampions": 18000,
        "challenges": challenges or {},
    }


def make_match(
    *,
    match_id: str = "NA1_4567890123",
    queue_id: int = 420,
    game_version: str = "14.20.581.1234",
    game_duration: float = 1620,  # seconds
    include_game_end_timestamp: bool = True,
    participants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if participants is None:
        participants = []
        for team_id in (100, 200):
            for i, position in enumerate(POSITIONS):
                pid = (0 if team_id == 100 else 5) + i + 1
                participants.append(
                    make_participant(pid, team_id=team_id, team_position=position, win=team_id == 100)
                )

    info: dict[str, Any] = {
        "queueId": queue_id,
        "gameVersion": game_version,
        "mapId": 11,
        "gameDuration": game_duration,
        "participants": participants,
    }
    if include_game_end_timestamp:
        info["gameEndTimestamp"] = 1_700_000_000_000

    return {"metadata": {"matchId": match_id, "participants": [p["puuid"] for p in participants]}, "info": info}


def make_participant_frame(
    participant_id: int,
    *,
    level: int = 6,
    current_gold: int = 500,
    total_gold: int = 3000,
    xp: int = 4000,
    minions_killed: int = 40,
    jungle_minions_killed: int = 0,
    position: tuple[int, int] | None = (5000, 5000),
) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "participantId": participant_id,
        "level": level,
        "currentGold": current_gold,
        "totalGold": total_gold,
        "xp": xp,
        "minionsKilled": minions_killed,
        "jungleMinionsKilled": jungle_minions_killed,
    }
    if position is not None:
        frame["position"] = {"x": position[0], "y": position[1]}
    return frame


def make_frame(
    timestamp_ms: int,
    participant_frames: dict[int, dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp_ms,
        "participantFrames": {str(pid): pf for pid, pf in participant_frames.items()},
        "events": events or [],
    }


def make_timeline(
    *,
    frame_interval_ms: int = 60_000,
    frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {"info": {"frameInterval": frame_interval_ms, "frames": frames or []}}
