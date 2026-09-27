"""Audit trail (hash chain) + live stream (SSE)."""
import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from .. import bus
from ..db import get_session
from ..models import AuditLog
from ..pipeline import audit

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit")
def log(entity: str | None = None, limit: int = 200, s: Session = Depends(get_session)):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    return s.exec(stmt.limit(limit)).all()


@router.post("/audit/verify")
def verify(s: Session = Depends(get_session)):
    return audit.verify_chain(s)


@router.get("/stream")
async def stream(request: Request):
    q = bus.subscribe()

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
