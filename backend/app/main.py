"""SiteSync API — `uvicorn app.main:app --reload --port 8000` (from /backend)."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from . import bus, config
from .api import analytics, audit, control, field, hse, review
from .db import init_db, session_scope
from .models import Activity


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus.bind_loop(asyncio.get_running_loop())
    init_db()
    with session_scope() as s:
        empty = s.exec(select(Activity).limit(1)).first() is None
    if empty:                                   # first run: build the demo site
        from .seed.run import reset
        await asyncio.to_thread(reset)
    if config.TELEGRAM_TOKEN:
        from .telegram_bot import start
        start()
    yield


app = FastAPI(title="SiteSync — field progress to schedule (SIH PS 122)", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (field.router, review.router, hse.router, analytics.router, audit.router, control.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "llm": bool(config.ANTHROPIC_API_KEY)}


# Serve the built frontend (single-port mode) if present.
dist = config.ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = dist / full_path
        if full_path and f.exists() and f.is_file():
            return FileResponse(f)
        return FileResponse(dist / "index.html")
