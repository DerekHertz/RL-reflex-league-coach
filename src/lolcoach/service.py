"""CoachService -- the one façade every frontend (API routes, CLI, a future
Discord bot) drives. Owns the Riot client, storage, and job runner; wires
detectors -> fact sheet -> narration -> cache into one background job.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from lolcoach.analysis.build import build_fact_sheet
from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.config import Settings, get_settings
from lolcoach.detectors.context import AnalysisContext
from lolcoach.detectors.registry import DETECTORS, engine_version
from lolcoach.detectors.runner import run_detectors
from lolcoach.domain.match import MatchView
from lolcoach.domain.timeline import TimelineIndex
from lolcoach.jobs.runner import Emit, JobRunner
from lolcoach.llm.narrator import narrate_match
from lolcoach.llm.schemas import CoachingResponse
from lolcoach.riot.cache import FileRawCache
from lolcoach.riot.client import RiotClient
from lolcoach.riot.rate_limiter import HeaderAwareLimiter
from lolcoach.storage import repo
from lolcoach.storage.db import init_db, make_engine, make_session_factory, session_scope


class CoachService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache = FileRawCache(self._settings.cache_dir)
        self._limiter = HeaderAwareLimiter()
        self._engine = make_engine(self._settings.db_path)
        self._session_factory = make_session_factory(self._engine)
        self._engine_version = engine_version()
        self.jobs = JobRunner()

    async def init(self) -> None:
        await init_db(self._engine)

    def start_analysis(self, riot_id: str, *, count: int = 20, queue: int | None = None) -> str:
        async def work(emit: Emit) -> dict[str, Any]:
            return await self._run_analysis(riot_id, count=count, queue=queue, emit=emit)

        return self.jobs.submit(work)

    def job_status(self, job_id: str):
        return self.jobs.get_state(job_id)

    def subscribe(self, job_id: str):
        return self.jobs.subscribe(job_id)

    async def _run_analysis(self, riot_id: str, *, count: int, queue: int | None, emit: Emit) -> dict[str, Any]:
        start = time.monotonic()
        emit("resolving", 0.02, f"Resolving {riot_id}...")
        async with httpx.AsyncClient(timeout=30.0) as http:
            client = RiotClient(api_key=self._settings.riot_api_key, limiter=self._limiter, cache=self._cache, http=http)
            player = await client.resolve_player(riot_id)

            async with session_scope(self._session_factory) as session:
                await repo.upsert_player(
                    session,
                    puuid=player.puuid,
                    game_name=player.game_name,
                    tag_line=player.tag_line,
                    platform=player.platform.value,
                    cluster=player.cluster.value,
                )

            emit("listing_matches", 0.05, "Fetching recent match list...")
            match_ids = await client.match_ids(player.puuid, player.cluster, count=count, queue=queue)
            if not match_ids:
                raise ValueError("No matches found for this player in the requested window/queue filter")

            total = len(match_ids)
            for i, match_id in enumerate(match_ids, start=1):
                frac = 0.05 + 0.55 * (i / total)
                emit("fetching", frac, f"Fetching match {i}/{total}: {match_id}")
                match_raw, _timeline_raw = await client.match_and_timeline(match_id)
                async with session_scope(self._session_factory) as session:
                    await self._index_match(session, match_raw)

        most_recent_id = match_ids[0]

        async with session_scope(self._session_factory) as session:
            cached_run = await repo.get_cached_analysis(
                session, match_id=most_recent_id, puuid=player.puuid, engine_version=self._engine_version
            )

        if cached_run is not None:
            emit("analyzing", 0.7, "Using a cached analysis for this match...")
            sheet = MatchFactSheet.model_validate_json(cached_run.fact_sheet_json)
            used_fallback = cached_run.used_fallback
            if cached_run.narrative_json is not None:
                narrative = CoachingResponse.model_validate_json(cached_run.narrative_json)
            else:
                emit("narrating", 0.85, "Asking Claude for coaching narration...")
                narrative, used_fallback = await narrate_match(sheet)
                await self._save_run(most_recent_id, player.puuid, sheet, narrative, used_fallback)
        else:
            emit("analyzing", 0.65, "Running detectors on the most recent match...")
            match_view = MatchView(self._cache.get("match", most_recent_id))  # type: ignore[arg-type]
            timeline_view = TimelineIndex(self._cache.get("timeline", most_recent_id))  # type: ignore[arg-type]
            ctx = AnalysisContext.build(match_view, timeline_view, player.puuid)
            results = run_detectors(ctx, DETECTORS)
            sheet = build_fact_sheet(ctx, results)

            emit("narrating", 0.75, "Asking Claude for coaching narration...")
            narrative, used_fallback = await narrate_match(sheet)
            await self._save_run(most_recent_id, player.puuid, sheet, narrative, used_fallback)

        elapsed_s = time.monotonic() - start
        emit("done", 1.0, "Done")
        return {
            "puuid": player.puuid,
            "match_id": most_recent_id,
            "other_match_ids": match_ids[1:],
            "fact_sheet": sheet.model_dump(mode="json"),
            "narrative": narrative.model_dump(mode="json"),
            "used_fallback": used_fallback,
            "model": "claude-opus-5",
            "elapsed_s": round(elapsed_s, 1),
        }

    async def _save_run(
        self, match_id: str, puuid: str, sheet: MatchFactSheet, narrative: CoachingResponse, used_fallback: bool
    ) -> None:
        async with session_scope(self._session_factory) as session:
            await repo.save_analysis_run(
                session,
                match_id=match_id,
                puuid=puuid,
                engine_version=self._engine_version,
                fact_sheet_json=sheet.model_dump_json(),
                narrative_json=narrative.model_dump_json(),
                used_fallback=used_fallback,
            )

    async def _index_match(self, session: AsyncSession, match_raw: dict) -> None:
        info = match_raw["info"]
        match_id = match_raw["metadata"]["matchId"]
        duration_s = MatchView(match_raw).duration_s
        await repo.upsert_match(
            session,
            match_id=match_id,
            platform=match_id.split("_")[0],
            queue_id=info["queueId"],
            game_version=info["gameVersion"],
            game_creation_ms=info["gameCreation"],
            duration_s=duration_s,
        )
        rows = [
            {
                "match_id": match_id,
                "puuid": p["puuid"],
                "participant_id": p["participantId"],
                "team_id": p["teamId"],
                "team_position": p.get("teamPosition", ""),
                "champion_id": p["championId"],
                "champion_name": p.get("championName", ""),
                "win": bool(p["win"]),
            }
            for p in info["participants"]
        ]
        await repo.upsert_match_participants(session, rows)
