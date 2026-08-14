from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from lolcoach.api.schemas import (
    ChampionsRequest,
    ChampionsResponse,
    ChatRequest,
    ChatResponse,
    JobStatusResponse,
    LedgerRequest,
    LedgerResponse,
    MetaResponse,
    PoolRequest,
    PoolResponse,
    StartAnalysisRequest,
    StartAnalysisResponse,
)
from lolcoach.detectors.registry import engine_version
from lolcoach.playstyle.archetypes import VALID_ROLES
from lolcoach.service import CoachService, NoIndexedHistoryError

router = APIRouter(prefix="/api")

DISCLAIMER = (
    "This tool isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games "
    "or anyone officially involved in producing or managing Riot Games properties."
)


def _service(request: Request) -> CoachService:
    return request.app.state.coach_service


@router.get("/meta", response_model=MetaResponse)
async def get_meta() -> MetaResponse:
    return MetaResponse(disclaimer=DISCLAIMER, engine_version=engine_version())


@router.post("/analysis", response_model=StartAnalysisResponse, status_code=202)
async def start_analysis(body: StartAnalysisRequest, request: Request) -> StartAnalysisResponse:
    service = _service(request)
    job_id = service.start_analysis(body.riot_id, count=body.count, queue=body.queue)
    return StartAnalysisResponse(job_id=job_id)


@router.get("/analysis/{job_id}", response_model=JobStatusResponse)
async def get_analysis_status(job_id: str, request: Request) -> JobStatusResponse:
    service = _service(request)
    try:
        state = service.job_status(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found") from None

    latest = state.latest
    return JobStatusResponse(
        status=state.status.value,
        progress=latest.progress if latest else 0.0,
        stage=latest.stage if latest else "queued",
        message=latest.message if latest else "queued",
        result=state.result,
        error=state.error,
    )


@router.post("/champions", response_model=ChampionsResponse)
async def get_champions(body: ChampionsRequest, request: Request) -> ChampionsResponse:
    """Playstyle vector + champion recommendations, computed purely from
    already-cached match JSON and the local match-participant index -- no
    Riot/Claude calls, so (unlike /api/analysis) this is a plain sync
    request/response rather than a background job with SSE progress; a warm
    cache answers in well under a second. See
    CoachService.get_champion_recommendations's docstring for the cold-cache
    (never-analyzed player) decision.
    """
    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"invalid role {body.role!r}; expected one of {VALID_ROLES}")

    service = _service(request)
    try:
        result = await service.get_champion_recommendations(body.riot_id, role=body.role)
    except NoIndexedHistoryError:
        raise HTTPException(
            status_code=404,
            detail=(
                "No indexed match history for this player yet. "
                "Run POST /api/analysis first to fetch and index their recent matches, then retry."
            ),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return ChampionsResponse(**result)


@router.post("/ledger", response_model=LedgerResponse)
async def get_ledger(body: LedgerRequest, request: Request) -> LedgerResponse:
    """Fired/total per detector across every match this player has ever had
    analyzed. Same cold-cache contract as /champions: 404s rather than
    kicking off a background fetch if the player has never run /api/analysis.
    """
    service = _service(request)
    try:
        entries = await service.get_ledger(body.riot_id)
    except NoIndexedHistoryError:
        raise HTTPException(
            status_code=404,
            detail=(
                "No indexed match history for this player yet. "
                "Run POST /api/analysis first to fetch and index their recent matches, then retry."
            ),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return LedgerResponse(entries=entries)


@router.post("/pool", response_model=PoolResponse)
async def get_pool(body: PoolRequest, request: Request) -> PoolResponse:
    """Fired/total per (champion, detector) cell across every analyzed
    match, grouped by champion. Same cold-cache contract as /champions and
    /ledger: 404s rather than kicking off a background fetch.
    """
    service = _service(request)
    try:
        champions = await service.get_pool(body.riot_id)
    except NoIndexedHistoryError:
        raise HTTPException(
            status_code=404,
            detail=(
                "No indexed match history for this player yet. "
                "Run POST /api/analysis first to fetch and index their recent matches, then retry."
            ),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return PoolResponse(champions=champions)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Stateless: no DB lookup, no puuid/match_id -- the fact sheet and
    narrative the frontend already holds from /api/analysis travel back in
    as the request body. See CoachService.answer_chat_question's docstring.
    """
    service = _service(request)
    result = await service.answer_chat_question(body.fact_sheet, body.narrative, body.question, body.history)
    return ChatResponse(**result)


@router.get("/analysis/{job_id}/events")
async def stream_analysis_events(job_id: str, request: Request) -> StreamingResponse:
    service = _service(request)
    try:
        events = service.subscribe(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found") from None

    async def event_stream():
        async for event in events:
            payload = {
                "stage": event.stage,
                "progress": event.progress,
                "message": event.message,
                "status": event.status.value,
                "result": event.result,
                "error": event.error,
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
