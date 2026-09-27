"""Field App + WhatsApp simulator endpoints. Worker-facing replies are plain words."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import clock, config
from ..db import get_session
from ..models import Event, Report, Reporter, WorkFront
from ..pipeline import ingest

router = APIRouter(prefix="/api/field", tags=["field"])


class ReportIn(BaseModel):
    text: str = ""
    reporter_id: str
    channel: str = "pwa"
    source_type: str | None = None             # chat | voice | whatsapp | photo | hse_form
    client_id: str | None = None               # offline-queue id → idempotent retries
    captured_at: datetime | None = None
    queued_at: datetime | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    gps_accuracy: float | None = None
    gps_timestamp: datetime | None = None
    photo_ids: list[str] = []
    transcript_raw: str | None = None
    audio_id: str | None = None
    device_id: str | None = None
    app_version: str | None = None
    safety: bool = False                       # the red "Safety report" button
    extras: dict | None = None                 # quick-add manpower / equipment / shift


def status_icon(e: Event) -> str:
    return {"linked": "recorded", "clarifying": "question", "hse_hold": "safety", "review": "checking", "unplanned": "checking",
            "duplicate": "recorded", "unparseable": "checking"}.get(e.state, "checking")


def summary(e: Event) -> dict:
    return {"id": e.id, "state": e.state, "status": status_icon(e), "text": e.source_sentence, "event_date": e.event_date,
            "question": e.clarification_asked if e.state == "clarifying" else None,
            "question_hi": (e.field_conf or {}).get("_question_hi") if e.state == "clarifying" else None,
            "options": e.clarification_options if e.state == "clarifying" else [],
            "activity": e.matched_activity_id}


@router.get("/me")
def me(reporter_id: str, s: Session = Depends(get_session)):
    r = s.get(Reporter, reporter_id)
    if not r:
        raise HTTPException(404, "unknown reporter")
    wfs = [s.get(WorkFront, w) for w in r.work_fronts or []]
    return {"reporter": r, "work_fronts": [{"id": w.id, "name": w.name, "unit": w.unit, "lat": w.centroid_lat, "lon": w.centroid_lon,
                                            "polygon": w.polygon} for w in wfs if w], "today": clock.today()}


@router.post("/photo")
async def upload_photo(file: UploadFile = File(...)):
    """Stores the original bytes untouched so EXIF (GPS + timestamp) survives."""
    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()[:5]
    safe = "".join(ch for ch in (file.filename or "photo").rsplit(".", 1)[0] if ch.isalnum() or ch in "-_")[:40]
    pid = f"{uuid.uuid4().hex[:8]}_{safe}.{ext}"
    (config.UPLOAD_DIR / pid).write_bytes(await file.read())
    return {"photo_id": pid}


@router.post("/report")
def report(body: ReportIn, s: Session = Depends(get_session)):
    if body.client_id:
        prev = s.exec(select(Report).where(Report.source_doc_id == body.client_id)).first()
        if prev:                                   # a retry from the offline queue — don't double-count
            evs = s.exec(select(Event).where(Event.report_id == prev.id)).all()
            return {"report_id": prev.id, "events": [summary(e) for e in evs], "reply": ingest.compose_reply(s, prev, evs), "duplicate_retry": True}
    text = body.text.strip()
    if body.extras:
        mp = body.extras.get("manpower") or {}
        bits = [f"{n} {t}" for t, n in mp.items() if n]
        if body.extras.get("equipment"):
            bits += list(body.extras["equipment"])
        if body.extras.get("shift") == "night":
            bits.append("night shift")
        if bits:
            text = (text + ", " if text else "") + ", ".join(bits)
    if body.safety and text and not any(w in text.lower() for w in ("near miss", "unsafe", "injur", "first aid", "fire", "spill", "stop work", "accident")):
        text = f"Safety observation: {text}"
    if not text and body.photo_ids:
        text = "Photo update"
    res = ingest.ingest(
        s, text=text, source_type=body.source_type or ("whatsapp" if body.channel == "whatsapp" else "chat"), channel=body.channel,
        reporter_id=body.reporter_id, captured_at=clock.shift(body.captured_at), queued_at=clock.shift(body.queued_at),
        gps_lat=body.gps_lat, gps_lon=body.gps_lon, gps_accuracy=body.gps_accuracy, gps_timestamp=clock.shift(body.gps_timestamp),
        photo_ids=body.photo_ids, transcript_raw=body.transcript_raw, audio_id=body.audio_id, device_id=body.device_id,
        app_version=body.app_version, source_doc_id=body.client_id)
    return {"report_id": res["report"].id, "events": [summary(e) for e in res["events"]], "reply": res["reply"]}


class ClarifyIn(BaseModel):
    event_id: int
    value: str
    photo_id: str | None = None


@router.post("/clarify")
def clarify(body: ClarifyIn, s: Session = Depends(get_session)):
    res = ingest.answer_clarification(s, body.event_id, body.value, body.photo_id)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error"))
    return {"event": summary(res["event"]), "reply": res["reply"]}


@router.get("/my-reports")
def my_reports(reporter_id: str, s: Session = Depends(get_session)):
    today = clock.today()
    reps = s.exec(select(Report).where(Report.reporter_id == reporter_id, Report.reporting_date == today).order_by(Report.id.desc())).all()
    out = []
    for r in reps:
        evs = s.exec(select(Event).where(Event.report_id == r.id)).all()
        out.append({"report_id": r.id, "at": r.captured_at, "channel": r.channel, "text": r.raw_text, "events": [summary(e) for e in evs],
                    "reply": ingest.compose_reply(s, r, evs)})
    return out


@router.get("/thread")
def thread(reporter_id: str, channel: str = "whatsapp", s: Session = Depends(get_session)):
    """Chat history for the WhatsApp simulator / chat screen (last 30 reports)."""
    reps = s.exec(select(Report).where(Report.reporter_id == reporter_id, Report.channel == channel).order_by(Report.id.desc()).limit(30)).all()
    out = []
    for r in reversed(reps):
        evs = s.exec(select(Event).where(Event.report_id == r.id)).all()
        out.append({"report_id": r.id, "at": r.captured_at, "text": r.transcript_raw or r.raw_text, "photos": r.photo_ids,
                    "events": [summary(e) for e in evs], "reply": ingest.compose_reply(s, r, evs)})
    return out
