from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.container import build_services


def create_app(settings=None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = build_services(resolved_settings)
        yield

    application = FastAPI(
        title="EvidenceTrail AI API",
        version="0.1.0",
        description="Evidence-first investigation workflow with deterministic demo mode.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin, "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)

    @application.get("/")
    def root() -> dict[str, str]:
        return {"name": "EvidenceTrail AI", "docs": "/docs", "health": "/api/health"}

    return application


app = create_app()
