from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lolcoach.storage.models import AnalysisRun, FindingOutcome, Match, MatchParticipant, Player

MIN_LEDGER_SAMPLE = 3


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
    champion_id: int | None = None,
    finding_outcomes: Sequence[tuple[str, str]] = (),
) -> AnalysisRun:
    """finding_outcomes is (detector_key, outcome) pairs for FINDINGS/CLEAN
    detector results only -- see FindingOutcome's docstring for why
    NOT_APPLICABLE/INSUFFICIENT_DATA/ERROR never appear here. Written in the
    same flush as the AnalysisRun row so the ledger is always consistent
    with what's cached; champion_id is required if finding_outcomes is
    non-empty.
    """
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

    if finding_outcomes:
        assert champion_id is not None, "champion_id is required when finding_outcomes is non-empty"
        session.add_all(
            FindingOutcome(analysis_run_id=run.id, puuid=puuid, champion_id=champion_id, detector_key=key, outcome=outcome)
            for key, outcome in finding_outcomes
        )
        await session.flush()

    return run


@dataclass(frozen=True, slots=True)
class LedgerRow:
    detector_key: str
    fired: int
    total: int
    rate: float | None


async def list_ledger_for_player(session: AsyncSession, *, puuid: str) -> list[LedgerRow]:
    """Fired/total per detector across every cached analysis for this
    player. `rate` is None below MIN_LEDGER_SAMPLE -- a rate computed from
    one or two matches is noise, not signal.
    """
    fired_case = func.sum(case((FindingOutcome.outcome == "FINDINGS", 1), else_=0))
    result = await session.execute(
        select(FindingOutcome.detector_key, fired_case.label("fired"), func.count().label("total"))
        .where(FindingOutcome.puuid == puuid)
        .group_by(FindingOutcome.detector_key)
    )
    return [
        LedgerRow(
            detector_key=detector_key,
            fired=fired,
            total=total,
            rate=(fired / total) if total >= MIN_LEDGER_SAMPLE else None,
        )
        for detector_key, fired, total in result.all()
    ]


async def list_analysis_runs_for_player(session: AsyncSession, *, puuid: str, limit: int = 20) -> list[AnalysisRun]:
    result = await session.execute(
        select(AnalysisRun).where(AnalysisRun.puuid == puuid).order_by(AnalysisRun.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
