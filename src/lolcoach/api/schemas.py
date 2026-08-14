"""API-facing DTOs -- mostly kept separate from MatchFactSheet/CoachingResponse
(different audience: these describe job lifecycle, not match content).
ChatRequest is the one exception: /api/chat is stateless (see service.py's
answer_chat_question), so the fact sheet + narrative the frontend already
holds from a prior /api/analysis response travel back in as the request
body verbatim, rather than being looked up server-side."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.llm.schemas import ChatTurn, CoachingResponse
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


class LedgerRequest(BaseModel):
    riot_id: str


class LedgerEntry(BaseModel):
    detector_key: str
    title: str
    fired: int
    total: int
    rate: float | None


class LedgerResponse(BaseModel):
    entries: list[LedgerEntry]


class PoolRequest(BaseModel):
    riot_id: str


class PoolChampionEntry(BaseModel):
    champion_id: int
    champion_name: str
    games_played: int
    entries: list[LedgerEntry]


class PoolResponse(BaseModel):
    champions: list[PoolChampionEntry]


class ChatRequest(BaseModel):
    fact_sheet: MatchFactSheet
    narrative: CoachingResponse
    question: str
    history: list[ChatTurn] = []


class ChatResponse(BaseModel):
    answer: str
    cited_finding_ids: list[str]
    used_fallback: bool
