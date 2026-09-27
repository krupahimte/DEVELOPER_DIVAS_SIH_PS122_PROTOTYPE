"""Control Room API: meta, events, schedule, uploads, DPR, ask, settings, unplanned, reset."""
import csv
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import clock, config
from ..db import get_session, get_settings, save_settings
from ..models import Activity, Alias, AuditLog, Event, HSEEvent, Report, Reporter, ReviewAction, WorkFront
from ..pipeline import ask, dpr, ingest, learning, spreadsheet, xer_parse
from ..pipeline.kg import get_kg

router = APIRouter(prefix="/api", tags=["control"])


@router.get("/meta")
def meta(s: Session = Depends(get_session)):
    kg = get_kg(s)
    return {"today": clock.today(), "now": clock.now(), "project": {"name": "Refinery Expansion — Assam (Units 2 & 3)", "lat": 27.47, "lon": 95.34},
            "reporters": s.exec(select(Reporter)).all(),
            "work_fronts": [{"id": w.id, "name": w.name, "unit": w.unit, "area": w.area, "polygon": w.polygon, "lat": w.centroid_lat,
                             "lon": w.centroid_lon} for w in s.exec(select(WorkFront))],
            "disciplines": ["Piping", "Civil", "Structural", "Electrical", "Instrumentation", "Mechanical"],
            "llm_available": bool(config.ANTHROPIC_API_KEY), "settings": get_settings(s), "kg": kg.stats()}


def ev_row(e: Event, kg) -> dict:
    return {"id": e.id, "report_id": e.report_id, "date": e.event_date, "state": e.state, "text": e.source_sentence, "channel": e.channel,
            "reporter_id": e.reporter_id, "discipline": e.discipline, "action": e.action, "object_event_type": e.object_event_type,
            "activity_inference": e.activity_inference, "activity": e.matched_activity_id, "blocker": e.blocker_flag, "cause": e.cause_category,
            "hse": e.hse_event_flag, "match_path": e.match_path, "margin": e.match_margin, "extraction_conf": e.extraction_conf,
            "match_conf": e.match_conf, "date_conf": e.date_conf, "verification_conf": e.verification_conf, "date_written": e.date_written,
            "work_front": e.location_zone_text or e.geofence_zone_id, "unplanned_class": e.unplanned_class, "route_reason": e.route_reason}


@router.get("/events")
def events(state: str | None = None, discipline: str | None = None, channel: str | None = None, reporter: str | None = None, q: str | None = None,
           date_from: date | None = None, date_to: date | None = None, cause: str | None = None, activity: str | None = None,
           match_path: str | None = None, ids: str | None = None, limit: int = 400, s: Session = Depends(get_session)):
    kg = get_kg(s)
    stmt = select(Event).order_by(Event.id.desc())
    if state:
        stmt = stmt.where(Event.state.in_(state.split(",")))
    if discipline:
        stmt = stmt.where(Event.discipline == discipline)
    if channel:
        stmt = stmt.where(Event.channel == channel)
    if reporter:
        stmt = stmt.where(Event.reporter_id == reporter)
    if date_from:
        stmt = stmt.where(Event.event_date >= date_from)
    if date_to:
        stmt = stmt.where(Event.event_date <= date_to)
    if cause:
        stmt = stmt.where(Event.cause_category == cause)
    if match_path:
        stmt = stmt.where(Event.match_path == match_path)
    rows = s.exec(stmt).all()
    if ids:
        want = {int(x) for x in ids.split(",") if x.strip().isdigit()}
        rows = [e for e in rows if e.id in want]
    if activity:
        rows = [e for e in rows if e.matched_activity_id == activity or activity in (e.affected_activities or [])]
    if q:
        ql = q.lower()
        rows = [e for e in rows if ql in (e.source_sentence or "").lower() or ql in (e.matched_activity_id or "").lower() or ql == str(e.id)]
    return [ev_row(e, kg) for e in rows[:limit]]


@router.get("/events/{eid}")
def event_detail(eid: int, s: Session = Depends(get_session)):
    e = s.get(Event, eid)
    if not e:
        raise HTTPException(404)
    r = s.get(Report, e.report_id)
    hse = s.exec(select(HSEEvent).where(HSEEvent.event_id == eid)).all()
    ras = s.exec(select(ReviewAction).where(ReviewAction.event_id == eid)).all()
    trail = s.exec(select(AuditLog).where(AuditLog.entity.in_([f"event:{eid}", f"report:{e.report_id}"])).order_by(AuditLog.id)).all()
    siblings = s.exec(select(Event.id).where(Event.report_id == e.report_id)).all()
    return {"event": e, "report": r, "hse": hse, "reviews": ras, "audit": trail, "siblings": siblings,
            "reporter": s.get(Reporter, e.reporter_id) if e.reporter_id else None}


@router.get("/activities")
def activities(s: Session = Depends(get_session)):
    kg = get_kg(s)
    today = clock.today()
    out = []
    evs = s.exec(select(Event).where(Event.matched_activity_id.is_not(None))).all()
    cnt = {}
    for e in evs:
        cnt[e.matched_activity_id] = cnt.get(e.matched_activity_id, 0) + 1
    for a in s.exec(select(Activity).order_by(Activity.activity_id)).all():
        vs = (a.actual_start - a.planned_start).days if a.actual_start else ((today - a.planned_start).days if a.planned_start < today else None)
        vf = (a.actual_finish - a.planned_finish).days if a.actual_finish else ((today - a.planned_finish).days if a.planned_finish < today else None)
        out.append({**a.model_dump(), "wf_name": kg.work_fronts[a.work_front].name if a.work_front else None, "var_start": vs, "var_finish": vf,
                    "status": "done" if a.actual_finish else ("in_progress" if a.actual_start else ("late" if a.planned_start < today else "planned")),
                    "event_count": cnt.get(a.activity_id, 0)})
    return out


@router.get("/schedule/export.csv")
def export_xer(s: Session = Depends(get_session)):
    """PMIS write-back: the XER-like CSV with the actual dates we wrote."""
    rows = xer_parse.to_csv_rows(s.exec(select(Activity).order_by(Activity.activity_id)).all())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=xer_parse.COLUMNS + ["act_start_source_event", "act_end_source_event"])
    w.writeheader()
    acts = {a.activity_id: a for a in s.exec(select(Activity))}
    for r in rows:
        a = acts[r["task_code"]]
        w.writerow({**r, "act_start_source_event": a.actual_start_source_event or "", "act_end_source_event": a.actual_finish_source_event or ""})
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=schedule_writeback.csv"})


# ───────────────────────────── uploads (DPR / spreadsheet / chat export) ─────────────────────────────

def _save(upload: UploadFile, data: bytes) -> str:
    name = f"{uuid.uuid4().hex[:8]}_{''.join(c for c in (upload.filename or 'file') if c.isalnum() or c in '._-')[:60]}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    return name


def _summ(res):
    return {"report_id": res["report"].id, "events": [{"id": e.id, "state": e.state, "text": e.source_sentence, "activity": e.matched_activity_id}
                                                      for e in res["events"]]}


@router.post("/upload/xlsx")
async def upload_xlsx(file: UploadFile = File(...), reporter_id: str | None = Form(None), s: Session = Depends(get_session)):
    data = await file.read()
    name = _save(file, data)
    parsed = spreadsheet.read(config.UPLOAD_DIR / name, clock.today())
    res = ingest.ingest(s, text=parsed["raw_text"], source_type="xlsx", channel="spreadsheet", reporter_id=reporter_id or None,
                        reporting_date=parsed["reporting_date"], extracted=parsed["events"], raw_file=name, source_doc_id=file.filename)
    return {**_summ(res), "header_row": parsed["header_row"], "mapping": list(parsed["mapping"].values()), "reporting_date": parsed["reporting_date"]}


@router.post("/upload/dpr")
async def upload_dpr(file: UploadFile = File(...), reporter_id: str | None = Form(None), s: Session = Depends(get_session)):
    data = await file.read()
    name = _save(file, data)
    if (file.filename or "").lower().endswith(".pdf"):
        text = spreadsheet.read_pdf_text(config.UPLOAD_DIR / name)
        st = "dpr_pdf"
    else:
        text = data.decode("utf-8", errors="replace")
        st = "dpr_text"
    import re
    m = re.search(r"(\d{1,2})[-/ ](\w{3})[-/ ](\d{4})", text)
    rdate = None
    if m:
        try:
            from datetime import datetime
            rdate = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").date()
        except ValueError:
            rdate = None
    rep = re.search(r"Reporter:\s*([A-Z]\.\s*\w+)", text)
    if rep and not reporter_id:
        r = s.exec(select(Reporter).where(Reporter.name == rep.group(1).strip())).first()
        reporter_id = r.id if r else None
    res = ingest.ingest(s, text=text, source_type=st, channel="dpr_upload", reporter_id=reporter_id or None, reporting_date=rdate,
                        raw_file=name, source_doc_id=file.filename, section_of=spreadsheet.dpr_sections(ingest.normalise(text)))
    return _summ(res)


@router.post("/upload/chat")
async def upload_chat(file: UploadFile = File(...), s: Session = Depends(get_session)):
    """WhatsApp chat export → one report per message, reporter matched by display name."""
    text = (await file.read()).decode("utf-8", errors="replace")
    reps = {r.name: r for r in s.exec(select(Reporter))}
    out = []
    for when, name, msg in spreadsheet.parse_chat_export(text):
        r = reps.get(name)
        res = ingest.ingest(s, text=msg, source_type="whatsapp", channel="whatsapp", reporter_id=r.id if r else None,
                            captured_at=when, queued_at=when, source_doc_id=file.filename)
        out.append(_summ(res))
    return {"reports": out}


@router.get("/samples")
def samples():
    files = sorted(p.name for p in config.SAMPLE_DIR.glob("*") if p.is_file())
    photos = sorted(p.name for p in (config.SAMPLE_DIR / "photos").glob("*.jpg"))
    return {"files": files, "photos": photos}


@router.get("/samples/{name}")
def sample_file(name: str):
    p = (config.SAMPLE_DIR / name)
    if not p.exists():
        p = config.SAMPLE_DIR / "photos" / name
    if not p.exists() or ".." in name:
        raise HTTPException(404)
    return Response(p.read_bytes(), headers={"Content-Disposition": f"inline; filename={name}"},
                    media_type="image/jpeg" if name.endswith(".jpg") else "application/octet-stream")


@router.get("/photos/{pid}")
def photo(pid: str):
    for p in (config.UPLOAD_DIR / pid, config.SAMPLE_DIR / "photos" / pid):
        if p.exists() and ".." not in pid:
            return Response(p.read_bytes(), media_type="image/jpeg")
    raise HTTPException(404)


# ───────────────────────────── DPR, Ask, Settings, Unplanned, Reset ─────────────────────────────

@router.get("/dpr")
def dpr_report(day: date, discipline: str | None = None, area: str | None = None, format: str = "html", s: Session = Depends(get_session)):
    d = dpr.gather(s, day, discipline or None, area or None)
    if format == "pdf":
        return Response(dpr.render_pdf(d), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename=DPR_{day.isoformat()}.pdf"})
    return HTMLResponse(dpr.render_html(d))


class AskIn(BaseModel):
    q: str


@router.post("/ask")
def ask_project(body: AskIn, s: Session = Depends(get_session)):
    return ask.answer(s, body.q)


@router.get("/settings")
def get_s(s: Session = Depends(get_session)):
    return get_settings(s)


@router.put("/settings")
def put_s(patch: dict, s: Session = Depends(get_session)):
    return save_settings(s, patch)


@router.get("/unplanned")
def unplanned(s: Session = Depends(get_session)):
    rows = s.exec(select(Event).where(Event.state == "unplanned").order_by(Event.id.desc())).all()
    return [{"id": e.id, "date": e.event_date, "text": e.source_sentence, "class": e.unplanned_class, "parent_wbs": e.suggested_parent_wbs,
             "change_order": e.change_order_candidate, "status": e.unplanned_status or "open", "reporter_id": e.reporter_id,
             "photo_ids": e.photo_ids, "zone": e.location_zone_text or e.geofence_zone_id, "top": e.top_k_candidates[:3], "channel": e.channel}
            for e in rows]


class UnplannedAct(BaseModel):
    action: str                    # link | propose | reopen
    activity_id: str | None = None
    reviewer: str = "R-MENON"


@router.post("/unplanned/{eid}")
def unplanned_act(eid: int, body: UnplannedAct, s: Session = Depends(get_session)):
    e = s.get(Event, eid)
    if not e:
        raise HTTPException(404)
    if body.action == "link":
        return learning.review(s, eid, "reassign", body.activity_id, "wrong_object", body.reviewer, None)
    e.unplanned_status = "proposed" if body.action == "propose" else "open"
    s.add(e)
    from ..pipeline import audit
    audit.append(s, body.reviewer, f"unplanned.{body.action}", f"event:{eid}", {"class": e.unplanned_class, "parent": e.suggested_parent_wbs})
    s.commit()
    return {"ok": True, "status": e.unplanned_status}


@router.get("/unplanned/proposals.csv")
def proposals(s: Session = Depends(get_session)):
    """New-activity proposals for the planner. We never author activity ids — the id column is left blank."""
    rows = s.exec(select(Event).where(Event.state == "unplanned", Event.unplanned_status == "proposed")).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["proposed_activity_id (planner to assign)", "suggested_parent_wbs", "description (verbatim)", "class", "change_order_candidate",
                "reported_on", "source_event"])
    for e in rows:
        w.writerow(["", e.suggested_parent_wbs, e.source_sentence, e.unplanned_class, e.change_order_candidate, e.event_date, f"EV-{e.id}"])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=unplanned_proposals.csv"})


@router.get("/aliases")
def aliases(s: Session = Depends(get_session)):
    return s.exec(select(Alias).order_by(Alias.id.desc())).all()


@router.post("/admin/reset")
def reset():
    from ..seed.run import reset as do_reset
    stats = do_reset(verbose=False)
    return {"ok": True, **stats}
