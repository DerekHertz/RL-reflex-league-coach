from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lolcoach.storage.models import AnalysisRun, Match, MatchParticipant, Player


async def upsert_player(
    session: AsyncSession, *, puuid: str, game_name: str, tag_line: str, platform: str, cluster: str
) -> None:
    stmt = sqlite_insert(Player).values(
        puuid=puuid, game_name=game_name, tag_line=tag_line, platform=platform, cluster=cluster, last_seen_at=datetime.now(UTC)
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Player.puuid],
        set_={"game_name": game_name, "tag_line": tag_line, "platform": platform, "cluster": cluster, "last_seen_at": datetime.now(UTC)},
    )
    await session.execute(stmt)


async def get_player_by_riot_id(session: AsyncSession, *, game_name: str, tag_line: str) -> Player | None:
    result = await session.execute(select(Player).where(Player.game_name == game_name, Player.tag_line == tag_line))
    return result.scalar_one_or_none()


async def upsert_match(
    session: AsyncSession,
    *,
    match_id: str,
    platform: str,
    queue_id: int,
    game_version: str,
    game_creation_ms: int,
    duration_s: float,
) -> None:
    stmt = sqlite_insert(Match).values(
        match_id=match_id,
        platform=platform,
        queue_id=queue_id,
        game_version=game_version,
        game_creation_ms=game_creation_ms,
        duration_s=duration_s,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[Match.match_id])
    await session.execute(stmt)


async def upsert_match_participants(session: AsyncSession, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = sqlite_insert(MatchParticipant).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=[MatchParticipant.match_id, MatchParticipant.puuid])
    await session.execute(stmt)


async def list_match_ids_for_player(session: AsyncSession, *, puuid: str, limit: int = 50) -> list[str]:
    """Match IDs indexed for this puuid (see service.py's `_index_match` --
    this covers every match a player's history was ever fetched for, not
    just ones that went through detectors/narration), most recent first.
    """
    result = await session.execute(
        select(MatchParticipant.match_id)
        .join(Match, Match.match_id == MatchParticipant.match_id)
        .where(MatchParticipant.puuid == puuid)
        .order_by(Match.game_creation_ms.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_cached_analysis(
    session: AsyncSession, *, match_id: str, puuid: str, engine_version: str
) -> AnalysisRun | None:
    result = await session.execute(
        select(AnalysisRun).where(
            AnalysisRun.match_id == match_id,
            AnalysisRun.puuid == puuid,
            AnalysisRun.engine_version == engine_version,
        )
    )
    return result.scalar_one_or_none()


async def save_analysis_run(
    session: AsyncSession,
    *,
    match_id: str,
    puuid: str,
    engine_version: str,
    fact_sheet_json: str,
    narrative_json: str | None,
    used_fallback: bool,
) -> AnalysisRun:
    run = AnalysisRun(
        match_id=match_id,
        puuid=puuid,
        engine_version=engine_version,
        fact_sheet_json=fact_sheet_json,
        narrative_json=narrative_json,
        used_fallback=used_fallback,
    )
    session.add(run)
    await session.flush()
    return run


async def list_analysis_runs_for_player(session: AsyncSession, *, puuid: str, limit: int = 20) -> list[AnalysisRun]:
    result = await session.execute(
        select(AnalysisRun).where(AnalysisRun.puuid == puuid).order_by(AnalysisRun.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
