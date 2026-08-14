"""SQLite schema.

Deliberately small for v1: match/timeline JSON already lives forever on the
filesystem cache (see riot/cache.py), and a fact sheet + narrative is cheap
to store as JSON blobs on `analysis_run` rather than normalized into
separate finding/metric tables. `finding_outcome` is the first normalized
table (added for the cross-match ledger, M8's original "cross-match trend
queries" motivation) -- it stores only the (detector, outcome) pair per
analysis run, not the full finding payload, so `analysis_run`'s JSON blobs
stay the source of truth. No Alembic: every table here is either a
cheap-to-rebuild index over the file cache or derived from a single
upstream call, so a schema change just means dropping and recreating the
(local, single-user) database file.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Player(Base):
    __tablename__ = "player"

    puuid: Mapped[str] = mapped_column(primary_key=True)
    game_name: Mapped[str]
    tag_line: Mapped[str]
    platform: Mapped[str]
    cluster: Mapped[str]
    last_seen_at: Mapped[datetime] = mapped_column(default=_now)

    __table_args__ = (UniqueConstraint("game_name", "tag_line"),)


class Match(Base):
    """An index over the raw match cache -- not the raw JSON itself."""

    __tablename__ = "match"

    match_id: Mapped[str] = mapped_column(primary_key=True)
    platform: Mapped[str]
    queue_id: Mapped[int]
    game_version: Mapped[str]
    game_creation_ms: Mapped[int]
    duration_s: Mapped[float]
    fetched_at: Mapped[datetime] = mapped_column(default=_now)


class MatchParticipant(Base):
    __tablename__ = "match_participant"

    match_id: Mapped[str] = mapped_column(ForeignKey("match.match_id"), primary_key=True)
    puuid: Mapped[str] = mapped_column(primary_key=True)
    participant_id: Mapped[int]
    team_id: Mapped[int]
    team_position: Mapped[str]
    champion_id: Mapped[int]
    champion_name: Mapped[str]
    win: Mapped[bool]


class AnalysisRun(Base):
    """One (match, subject, detector-set-version) analysis, cached so a page
    refresh or a repeat request never re-fetches from Riot or re-calls Claude.
    """

    __tablename__ = "analysis_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("match.match_id"))
    puuid: Mapped[str]
    engine_version: Mapped[str]
    fact_sheet_json: Mapped[str]
    narrative_json: Mapped[str | None] = mapped_column(default=None)
    used_fallback: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    __table_args__ = (UniqueConstraint("match_id", "puuid", "engine_version"),)


class FindingOutcome(Base):
    """One (detector, analysis_run) outcome row -- feeds the cross-match
    ledger (GROUP BY puuid, detector_key) and the future per-champion pool
    grid (GROUP BY puuid, champion_id, detector_key) off the same table.

    Only FINDINGS/CLEAN outcomes get a row here. NOT_APPLICABLE,
    INSUFFICIENT_DATA, and ERROR all mean the detector didn't evaluate, not
    that it "didn't fire" -- excluding them at write time means every
    fired/total ratio computed from this table is correct by construction,
    with no outcome-filtering to get right (or wrong) at every call site.
    """

    __tablename__ = "finding_outcome"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_run.id"))
    puuid: Mapped[str]
    champion_id: Mapped[int]
    detector_key: Mapped[str]
    outcome: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=_now)

    __table_args__ = (Index("ix_finding_outcome_puuid_detector", "puuid", "detector_key"),)
