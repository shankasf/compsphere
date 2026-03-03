import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize logging FIRST, before any other imports that use logging
from core.logging_config import setup_logging, get_logger
setup_logging()

from middleware.request_logging import RequestLoggingMiddleware
from models.database import Base, engine
from routers import auth, tasks
from routers import ws as ws_router
from routers import client_logs
from services.docker_manager import DockerManager
from services.session_manager import SessionManager
from services.agent_orchestrator import AgentOrchestrator

logger = get_logger("compsphere.app")

app = FastAPI(title="CompSphere API", version="0.1.0")

# Middleware order matters: request logging wraps everything
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
docker_manager = DockerManager()
session_manager = SessionManager(docker_manager)
agent_orchestrator = AgentOrchestrator()

# Wire services into routers
ws_router.session_manager = session_manager
ws_router.agent_orchestrator = agent_orchestrator
tasks.session_manager = session_manager
tasks.agent_orchestrator = agent_orchestrator

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(ws_router.router, tags=["websocket"])
app.include_router(client_logs.router, prefix="/api/client-logs", tags=["client-logs"])


@app.on_event("startup")
async def startup():
    # Import all models so Base.metadata knows about every table
    import models.session  # noqa: F401
    import models.task  # noqa: F401
    import models.user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("CompSphere API started successfully")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": session_manager.get_active_count(),
    }
