"""Contract test for POST /api/champions -- the playstyle vector +
recommendations endpoint. No LLM call on this path at all, but the
rationale strings are still user-facing prose, so this mirrors the
content-lint spirit of tests/llm/test_guard.py's forbidden-term check even
though nothing here ever reaches Claude.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lolcoach.api.routes import router
from lolcoach.config import Settings
from lolcoach.riot.cache import FileRawCache
from lolcoach.service import CoachService
from lolcoach.storage import repo
from lolcoach.storage.db import init_db, make_engine, make_session_factory, session_scope
from tests.builders import MatchBuilder

# Same spirit as llm/guard.py's _FORBIDDEN_TERMS: rank-tier/MMR language has
# no place in playstyle rationale either, and neither does "score" language
# implying a single overall rating (fit_score is a numeric API field, never
# quoted inside the rationale text itself).
_FORBIDDEN_RATIONALE_TERMS = re.compile(
    r"\b(iron|bronze|silver|platinum|emerald|diamond|master|grandmaster|challenger|mmr|elo|rank|tier|score)\b",
    re.IGNORECASE,
)

_AXES = ("aggression", "farming", "vision", "objective_focus", "risk_tolerance", "teamfight_vs_split")


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


def _seed_player_and_matches(db_path: Path, *, puuid: str, game_name: str, tag_line: str, raws: list[dict]) -> None:
    """Populate the DB the same way service._index_match would, but without
    going through the Riot client -- this test builds a fully synthetic
    scenario (see module docstring) rather than depending on the real
    git-ignored cache/ dir having data.
    """

    async def _run() -> None:
        engine = make_engine(db_path)
        await init_db(engine)
        factory = make_session_factory(engine)
        async with session_scope(factory) as session:
            await repo.upsert_player(
                session, puuid=puuid, game_name=game_name, tag_line=tag_line, platform="na1", cluster="americas"
            )
            for raw in raws:
                info = raw["info"]
                match_id = raw["metadata"]["matchId"]
                await repo.upsert_match(
                    session,
                    match_id=match_id,
                    platform=match_id.split("_")[0],
                    queue_id=info["queueId"],
                    game_version=info["gameVersion"],
                    game_creation_ms=0,
                    duration_s=1800,
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
        await engine.dispose()

    asyncio.run(_run())


def _build_and_cache_matches(cache: FileRawCache, *, puuid: str, count: int) -> list[dict]:
    raws = []
    for i in range(count):
        match = (
            MatchBuilder()
            .match_id(f"NA1_CONTRACT_{i}")
            .with_full_lobby(
                puuid=puuid,
                challenges={"killParticipation": 0.45, "soloKills": 2, "teamDamagePercentage": 0.22},
            )
            .build()
        )
        cache.put("match", match.match_id, match.raw)
        raws.append(match.raw)
    return raws


def test_champions_endpoint_returns_playstyle_and_recommendations(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    db_path = tmp_path / "test.db"
    cache = FileRawCache(cache_dir)
    raws = _build_and_cache_matches(cache, puuid="PUUID_SUBJECT", count=6)
    _seed_player_and_matches(db_path, puuid="PUUID_SUBJECT", game_name="Tester", tag_line="NA1", raws=raws)

    app = _make_app(Settings(cache_dir=cache_dir, db_path=db_path))
    with TestClient(app) as client:
        resp = client.post("/api/champions", json={"riot_id": "Tester#NA1"})

    assert resp.status_code == 200
    body = resp.json()

    assert set(body.keys()) == {"playstyle", "recommendations", "sample_size"}
    assert body["sample_size"] == 6
    playstyle = body["playstyle"]
    for axis in _AXES:
        assert axis in playstyle
        assert 0.0 <= playstyle[axis] <= 1.0
    assert 0.0 <= playstyle["confidence"] <= 1.0
    assert playstyle["sample_size"] == 6

    recs = body["recommendations"]
    assert len(recs) >= 1
    kinds = {r["kind"] for r in recs}
    assert kinds <= {"comfort", "stretch"}
    for rec in recs:
        assert isinstance(rec["champion"], str) and rec["champion"]
        assert isinstance(rec["roles"], list) and rec["roles"]
        assert isinstance(rec["fit_score"], float)
        assert isinstance(rec["rationale"], str) and rec["rationale"]
        assert not _FORBIDDEN_RATIONALE_TERMS.search(rec["rationale"]), rec["rationale"]
        if rec["kind"] == "stretch":
            assert rec["stretch_axis"] in _AXES
        else:
            assert rec["stretch_axis"] is None


def test_champions_endpoint_role_filter(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    db_path = tmp_path / "test.db"
    cache = FileRawCache(cache_dir)
    raws = _build_and_cache_matches(cache, puuid="PUUID_SUBJECT", count=6)
    _seed_player_and_matches(db_path, puuid="PUUID_SUBJECT", game_name="Tester", tag_line="NA1", raws=raws)

    app = _make_app(Settings(cache_dir=cache_dir, db_path=db_path))
    with TestClient(app) as client:
        resp = client.post("/api/champions", json={"riot_id": "Tester#NA1", "role": "UTILITY"})

    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert recs  # UTILITY has >= 6 champions in the real roster
    for rec in recs:
        assert "UTILITY" in rec["roles"]


def test_champions_endpoint_rejects_invalid_role(tmp_path: Path) -> None:
    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/champions", json={"riot_id": "Tester#NA1", "role": "CARRY"})
    assert resp.status_code == 400


def test_champions_endpoint_404s_for_player_with_no_indexed_history(tmp_path: Path) -> None:
    app = _make_app(Settings(cache_dir=tmp_path / "cache", db_path=tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/champions", json={"riot_id": "NeverAnalyzed#NA1"})
    assert resp.status_code == 404
