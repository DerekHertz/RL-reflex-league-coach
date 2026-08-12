from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from lolcoach.api.schemas import JobStatusResponse, MetaResponse, StartAnalysisRequest, StartAnalysisResponse
from lolcoach.detectors.registry import engine_version
from lolcoach.service import CoachService

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
