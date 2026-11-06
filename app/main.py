"""H3 Prompt Studio Main Application Entrypoint.

Normative Reference: specification-0.3.md §§5.1, 5.6, 5.6.1, 5.7, 17.2
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
import httpx

from app.config import (
    ALLOWED_HOST,
    DEFAULT_PORT,
    SPECIFICATION_VERSION,
    ensure_directories,
    resolve_listen_port,
    verify_host,
)
from app.middleware.security import SecurityMiddleware
from app.storage.db import get_db_connection
from app.storage.migration_runner import get_current_schema_version, run_migrations
import app.validation.rules  # Ensure all PF rules are registered in default_registry
from app.api.validation_routes import router as validation_router
from app.api.export_routes import router as export_router
from app.api.llm_routes import router as llm_router
from app.api.t2va_routes import router as t2va_router
from app.api.frame_routes import router as frame_router
from app.api.ref2va_routes import router as ref2va_router
from app.llm.lock import recover_generating_clips_on_startup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("h3studio")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle hooks: directory creation, migrations, and port resolution."""
    # 1. Verify host configuration (§5.7)
    verify_host()

    # 2. Ensure runtime directories exist (§17.2)
    ensure_directories()

    # 3. Apply database migrations (§5.7)
    schema_version = run_migrations()
    app.state.schema_version = schema_version
    logger.info("Database initialized at schema_version: %d", schema_version)

    # 4. Startup crash recovery (§5.5, §5.7)
    recover_generating_clips_on_startup()

    # 5. Resolve process listen port (§5.7)
    bound_port = resolve_listen_port()
    app.state.bound_port = bound_port
    logger.info("Bound to loopback: http://%s:%d", ALLOWED_HOST, bound_port)

    yield


app = FastAPI(
    title="H3 Prompt Studio",
    version=SPECIFICATION_VERSION,
    lifespan=lifespan,
)

# Mount security middleware
app.add_middleware(SecurityMiddleware)

# Mount API routers
app.include_router(validation_router)
app.include_router(export_router)
app.include_router(llm_router)
app.include_router(t2va_router)
app.include_router(frame_router)
app.include_router(ref2va_router)

# Mount Web Shell Static Assets (§4.1–§4.3)
WEB_DIR = Path(__file__).resolve().parent / "web"

@app.get("/", response_class=FileResponse)
async def serve_index():
    index_path = WEB_DIR / "index.html"
    return FileResponse(str(index_path))

app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")


@app.get("/api/health")
async def health_check(request: Request) -> JSONResponse:
    """System health check endpoint per specification-0.3.md §5.6.1:

    Returns status, specification_version ("0.3"), schema_version,
    ollama reachability, model count, and bind address string.
    """
    bound_port = getattr(request.app.state, "bound_port", DEFAULT_PORT)
    schema_version = getattr(request.app.state, "schema_version", 0)

    # If schema_version was not cached in state, query DB directly or run migrations
    if not schema_version:
        try:
            schema_version = run_migrations()
            request.app.state.schema_version = schema_version
        except Exception:
            try:
                conn = get_db_connection()
                schema_version = get_current_schema_version(conn)
                conn.close()
            except Exception:
                schema_version = 0

    # Probe local Ollama endpoint (§5.6.1)
    ollama_status = "unreachable"
    model_count = 0
    try:
        async with httpx.AsyncClient(timeout=0.8) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_status = "reachable"
                data = resp.json()
                models = data.get("models", [])
                model_count = len(models)
    except Exception:
        ollama_status = "unreachable"
        model_count = 0

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "specification_version": SPECIFICATION_VERSION,
            "schema_version": schema_version,
            "ollama": ollama_status,
            "model_count": model_count,
            "bind": f"{ALLOWED_HOST}:{bound_port}",
        },
    )


def create_app() -> FastAPI:
    """Factory creating the configured FastAPI instance."""
    return app
