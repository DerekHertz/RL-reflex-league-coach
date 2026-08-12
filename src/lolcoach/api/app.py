from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lolcoach.api.routes import router
from lolcoach.service import CoachService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    service = CoachService()
    await service.init()
    app.state.coach_service = service
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="LoL Coach", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
