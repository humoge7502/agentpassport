"""AgentPassport API — application factory (spec §41/§48/§71)."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger import json as jsonlogger

from app.api_agents import router as agents_router
from app.api_deps import correlation_id as corr_id_dep
from app.api_misc import (
    audit_router, policy_router, router as misc_router, security_router,
)
from app.api_mcp import router as mcp_router
from app.api_trust import router as trust_router
from app.config import get_settings
from app.services import get_services

logger = logging.getLogger("agentpassport")


def _setup_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s", rename_fields={
            "asctime": "ts", "levelname": "level", "name": "logger",
        },
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    services = get_services()
    # register platform key row so its signatures resolve
    from sqlalchemy import select
    from app.models import SigningKey
    kid, _priv = services.keys._platform()  # noqa: SLF001 — boot-time wiring
    with services.db.session() as db:
        exists = db.execute(
            select(SigningKey).where(SigningKey.key_id == kid)
        ).scalars().first()
        if exists is None:
            from app.domain.crypto import KeyPair
            pub = services.keys.store.get(kid)
            # derive public from private
            from nacl.signing import SigningKey as _SK
            import base64
            sk = _SK(base64.b64decode(pub))
            pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
            db.add(SigningKey(key_id=kid, scope="platform",
                              public_key_b64=pub_b64, status="active"))
            db.commit()
    if settings.jobs_enabled:
        from app.jobs import start_scheduler
        start_scheduler(services)
    logger.info("agentpassport.started", extra={"env": settings.env})
    yield
    logger.info("agentpassport.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    _setup_logging()
    app = FastAPI(
        title="AgentPassport API",
        version="1.0.0",
        description="Trust infrastructure for autonomous AI agents: identity, "
                    "evidence, capability-conditioned reputation, trust decisions.",
        lifespan=lifespan,
        docs_url="/api/docs", openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def observability(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "http.request",
            extra={"method": request.method, "path": request.url.path,
                   "status": response.status_code, "duration_ms": round(elapsed_ms, 1)},
        )
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
        return response

    # structured error envelope (spec §71) — never leak internals
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("http.unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error",
                     "message": "an internal error occurred",
                     "correlation_id": request.headers.get("x-correlation-id")},
        )

    prefix = settings.api_prefix
    app.include_router(agents_router, prefix=prefix)
    app.include_router(trust_router, prefix=prefix)
    app.include_router(misc_router, prefix=prefix)
    app.include_router(policy_router, prefix=prefix)
    app.include_router(security_router, prefix=prefix)
    app.include_router(audit_router, prefix=prefix)
    app.include_router(mcp_router, prefix=prefix)

    # --- health/readiness (spec §48) ------------------------------------------
    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "agentpassport"}

    @app.get("/ready", tags=["system"])
    def ready():
        services = get_services()
        try:
            with services.db.session() as db:
                db.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception:
            return JSONResponse(status_code=503,
                                content={"status": "not_ready", "database": "error"})

    return app


app = create_app()
