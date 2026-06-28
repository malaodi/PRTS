from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.auth import router as auth_router
from app.api.spaces import router as spaces_router
from app.api.agent import router as agent_router
from app.api.assets import router as assets_router
from app.api.credentials import router as credentials_router
from app.api.hub import router as hub_router
from app.api.pipelines import router as pipelines_router
from app.api.agents import router as agents_router
from app.api.channels import router as channels_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(spaces_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    app.include_router(credentials_router, prefix="/api/v1")
    app.include_router(hub_router, prefix="/api/v1")
    app.include_router(pipelines_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(channels_router, prefix="/api/v1")

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "name": settings.APP_NAME}

    return app


app = create_app()
