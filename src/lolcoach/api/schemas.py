"""API-facing DTOs -- kept separate from MatchFactSheet/CoachingResponse
(different audience: these describe job lifecycle, not match content)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from lolcoach.playstyle.recommend import ChampionRec
from lolcoach.playstyle.vector import PlaystyleVector


class StartAnalysisRequest(BaseModel):
    riot_id: str
    count: int = 20
    queue: int | None = None


class StartAnalysisResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    status: str
    progress: float
    stage: str
    message: str
    result: dict[str, Any] | None = None
    error: str | None = None


class MetaResponse(BaseModel):
    disclaimer: str
    engine_version: str


class ChampionsRequest(BaseModel):
    riot_id: str
    role: str | None = None


class ChampionsResponse(BaseModel):
    playstyle: PlaystyleVector
    recommendations: list[ChampionRec]
    sample_size: int
