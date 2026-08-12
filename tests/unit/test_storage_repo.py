import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import StaticPool

from lolcoach.storage import repo
from lolcoach.storage.db import init_db, make_engine, make_session_factory, session_scope


@pytest_asyncio.fixture
async def session_factory() -> async_sessionmaker:
    from sqlalchemy.ext.asyncio import create_async_engine

    # StaticPool -- an in-memory sqlite DB is per-connection; without a
    # shared pool each checkout would see an empty database.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    await init_db(engine)
    yield make_session_factory(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_player_then_lookup(session_factory) -> None:
    async with session_scope(session_factory) as session:
        await repo.upsert_player(session, puuid="P1", game_name="Foo", tag_line="NA1", platform="na1", cluster="americas")

    async with session_scope(session_factory) as session:
        player = await repo.get_player_by_riot_id(session, game_name="Foo", tag_line="NA1")
    assert player is not None
    assert player.puuid == "P1"


@pytest.mark.asyncio
async def test_upsert_player_is_idempotent_on_conflict(session_factory) -> None:
    async with session_scope(session_factory) as session:
        await repo.upsert_player(session, puuid="P1", game_name="Foo", tag_line="NA1", platform="na1", cluster="americas")
        await repo.upsert_player(session, puuid="P1", game_name="FooRenamed", tag_line="NA1", platform="na1", cluster="americas")

    async with session_scope(session_factory) as session:
        player = await repo.get_player_by_riot_id(session, game_name="FooRenamed", tag_line="NA1")
    assert player is not None
    assert player.puuid == "P1"


@pytest.mark.asyncio
async def test_analysis_run_cache_roundtrip(session_factory) -> None:
    async with session_scope(session_factory) as session:
        await repo.upsert_match(
            session, match_id="NA1_1", platform="NA1", queue_id=420, game_version="14.20.1", game_creation_ms=0, duration_s=1800
        )

    async with session_scope(session_factory) as session:
        missing = await repo.get_cached_analysis(session, match_id="NA1_1", puuid="P1", engine_version="v1")
    assert missing is None

    async with session_scope(session_factory) as session:
        await repo.save_analysis_run(
            session,
            match_id="NA1_1",
            puuid="P1",
            engine_version="v1",
            fact_sheet_json="{}",
            narrative_json="{}",
            used_fallback=False,
        )

    async with session_scope(session_factory) as session:
        found = await repo.get_cached_analysis(session, match_id="NA1_1", puuid="P1", engine_version="v1")
    assert found is not None
    assert found.fact_sheet_json == "{}"


@pytest.mark.asyncio
async def test_analysis_run_cache_is_keyed_by_engine_version(session_factory) -> None:
    # A detector version bump changes engine_version -- the old cached run
    # must NOT be served for the new version.
    async with session_scope(session_factory) as session:
        await repo.upsert_match(
            session, match_id="NA1_1", platform="NA1", queue_id=420, game_version="14.20.1", game_creation_ms=0, duration_s=1800
        )
        await repo.save_analysis_run(
            session, match_id="NA1_1", puuid="P1", engine_version="v1", fact_sheet_json="{}", narrative_json=None, used_fallback=False
        )

    async with session_scope(session_factory) as session:
        found_old = await repo.get_cached_analysis(session, match_id="NA1_1", puuid="P1", engine_version="v1")
        found_new = await repo.get_cached_analysis(session, match_id="NA1_1", puuid="P1", engine_version="v2")
    assert found_old is not None
    assert found_new is None


@pytest.mark.asyncio
async def test_upsert_match_participants(session_factory) -> None:
    async with session_scope(session_factory) as session:
        await repo.upsert_match(
            session, match_id="NA1_1", platform="NA1", queue_id=420, game_version="14.20.1", game_creation_ms=0, duration_s=1800
        )
        await repo.upsert_match_participants(
            session,
            [
                {
                    "match_id": "NA1_1",
                    "puuid": "P1",
                    "participant_id": 1,
                    "team_id": 100,
                    "team_position": "TOP",
                    "champion_id": 1,
                    "champion_name": "Annie",
                    "win": True,
                }
            ],
        )
        # Repeat upsert with the same key must not raise (on_conflict_do_nothing).
        await repo.upsert_match_participants(
            session,
            [
                {
                    "match_id": "NA1_1",
                    "puuid": "P1",
                    "participant_id": 1,
                    "team_id": 100,
                    "team_position": "TOP",
                    "champion_id": 1,
                    "champion_name": "Annie",
                    "win": True,
                }
            ],
        )
