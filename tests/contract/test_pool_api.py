"""Contract test for POST /api/pool -- fired/total per (champion, detector)
cell. Seeds AnalysisRun + MatchParticipant + finding_outcome rows directly
via repo functions, same spirit as test_ledger_api.py: no Riot or LLM calls
on this path.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lolcoach.api.routes import router
from lolcoach.config import Settings
from lolcoach.service import CoachService
from lolcoach.storage import repo
from lolcoach.storage.db import init_db, make_engine, make_session_factory, session_scope


def _make_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = CoachService(settings)
        await service.init()
        app.state.coach_service = service
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app


def _seed(
    db_path: Path,
    *,
    puuid: str,
    game_name: str,
    tag_line: str,
    runs: list[tuple[str, int, str, list[tuple[str, str]]]],
) -> None:
    """runs is [(match_id, champion_id, champion_name, [(detector_key, outcome), ...]), ...]."""

    async def _run() -> None:
        engine = make_engine(db_path)
        await init_db(engine)
        factory = make_session_factory(engine)
        async with session_scope(factory) as session:
            await repo.upsert_player(session, puuid=puuid, game_name=game_name, tag_line=tag_line, platform="na1", cluster="americas")
            for i, (match_id, champion_id, champion_name, finding_outcomes) in enumerate(runs):
                await repo.upsert_match(
                    session, match_id=match_id, platform="NA1", queue_id=420, game_version="14.20.1", game_creation_ms=i, duration_s=1800
                )
                await repo.upsert_match_participants(
                    session,
                    [
                        {
                            "match_id": match_id,
                            "puuid": puuid,
                            "participant_id": 1,
                            "team_id": 100,
                            "team_position": "TOP",
                            "champion_id": champion_id,
                            "champion_name": champion_name,
                            "win": True,
                        }
                    ],
                )
                await repo.save_analysis_run(
                    session,
                    match_id=match_id,
                    puuid=puuid,
                    engine_version="v1",
                    fact_sheet_json="{}",
                    narrative_json="{}",
                    used_fallback=False,
                    champion_id=champion_id,
                    finding_outcomes=finding_outcomes,
                )
        await engine.dispose()

    asyncio.run(_run())


def test_pool_endpoint_groups_by_champion_most_played_first(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _seed(
        db_path,
        puuid="PUUID_SUBJECT",
        game_name="Tester",
        tag_line="NA1",
        runs=[
            ("NA1_0", 1, "Annie", [("unspent_gold", "FINDINGS")]),
            ("NA1_1", 1, "Annie", [("unspent_gold", "FINDINGS")]),
            ("NA1_2", 1, "Annie", [("unspent_gold", "CLEAN")]),
            ("NA1_3", 2, "Ahri", [("unspent_gold", "CLEAN")]),
        ],
    )

    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=db_path))
    with TestClient(app) as client:
        resp = client.post("/api/pool", json={"riot_id": "Tester#NA1"})

    assert resp.status_code == 200
    champions = resp.json()["champions"]
    assert [c["champion_name"] for c in champions] == ["Annie", "Ahri"]

    annie = champions[0]
    assert annie["games_played"] == 3
    annie_entry = next(e for e in annie["entries"] if e["detector_key"] == "unspent_gold")
    assert annie_entry["fired"] == 2
    assert annie_entry["total"] == 3
    assert annie_entry["rate"] == 2 / 3
    assert annie_entry["title"] == "Sitting on gold"

    ahri = champions[1]
    assert ahri["games_played"] == 1
    ahri_entry = next(e for e in ahri["entries"] if e["detector_key"] == "unspent_gold")
    assert ahri_entry["rate"] is None  # below min sample for this champion


def test_pool_endpoint_404s_for_player_with_no_indexed_history(tmp_path: Path) -> None:
    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/pool", json={"riot_id": "NeverAnalyzed#NA1"})
    assert resp.status_code == 404
