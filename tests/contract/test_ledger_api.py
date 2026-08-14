"""Contract test for POST /api/ledger -- fired/total per detector across a
player's analyzed matches. Seeds AnalysisRun + finding_outcome rows directly
via repo.save_analysis_run, same spirit as test_champions_api.py: no Riot or
LLM calls on this path, so nothing needs mocking beyond the DB.
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


def _seed(db_path: Path, *, puuid: str, game_name: str, tag_line: str, runs: list[tuple[str, list[tuple[str, str]]]]) -> None:
    """runs is [(match_id, [(detector_key, outcome), ...]), ...] -- one
    AnalysisRun + its finding_outcome rows per entry.
    """

    async def _run() -> None:
        engine = make_engine(db_path)
        await init_db(engine)
        factory = make_session_factory(engine)
        async with session_scope(factory) as session:
            await repo.upsert_player(session, puuid=puuid, game_name=game_name, tag_line=tag_line, platform="na1", cluster="americas")
            for i, (match_id, finding_outcomes) in enumerate(runs):
                await repo.upsert_match(
                    session, match_id=match_id, platform="NA1", queue_id=420, game_version="14.20.1", game_creation_ms=i, duration_s=1800
                )
                await repo.save_analysis_run(
                    session,
                    match_id=match_id,
                    puuid=puuid,
                    engine_version="v1",
                    fact_sheet_json="{}",
                    narrative_json="{}",
                    used_fallback=False,
                    champion_id=1,
                    finding_outcomes=finding_outcomes,
                )
        await engine.dispose()

    asyncio.run(_run())


def test_ledger_endpoint_returns_fired_total_and_rate(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _seed(
        db_path,
        puuid="PUUID_SUBJECT",
        game_name="Tester",
        tag_line="NA1",
        runs=[
            ("NA1_0", [("unspent_gold", "FINDINGS")]),
            ("NA1_1", [("unspent_gold", "FINDINGS")]),
            ("NA1_2", [("unspent_gold", "CLEAN")]),
        ],
    )

    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=db_path))
    with TestClient(app) as client:
        resp = client.post("/api/ledger", json={"riot_id": "Tester#NA1"})

    assert resp.status_code == 200
    entries = {e["detector_key"]: e for e in resp.json()["entries"]}
    row = entries["unspent_gold"]
    assert row["fired"] == 2
    assert row["total"] == 3
    assert row["rate"] == 2 / 3
    assert row["title"] == "Sitting on gold"


def test_ledger_endpoint_below_min_sample_has_null_rate(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _seed(
        db_path,
        puuid="PUUID_SUBJECT",
        game_name="Tester",
        tag_line="NA1",
        runs=[("NA1_0", [("ward_drought", "FINDINGS")])],
    )

    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=db_path))
    with TestClient(app) as client:
        resp = client.post("/api/ledger", json={"riot_id": "Tester#NA1"})

    assert resp.status_code == 200
    row = next(e for e in resp.json()["entries"] if e["detector_key"] == "ward_drought")
    assert row["total"] == 1
    assert row["rate"] is None


def test_ledger_endpoint_404s_for_player_with_no_indexed_history(tmp_path: Path) -> None:
    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/ledger", json={"riot_id": "NeverAnalyzed#NA1"})
    assert resp.status_code == 404
