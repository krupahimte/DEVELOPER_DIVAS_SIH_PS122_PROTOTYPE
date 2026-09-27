"""End-of-day DPR reconstruction (spec §4.12).

Built only from the day's events. Every line cites its source event (EV-n), blockers
keep their verbatim cause_text, HSE text is never paraphrased, and weather shows the
claim next to the fetched record.
"""
import html
from collections import defaultdict
from datetime import date
from io import BytesIO

from sqlmodel import Session, select

from ..models import Activity, Event, HSEEvent, Reporter
from .kg import get_kg


def gather(session: Session, day: date, discipline: str | None = None, area: str | None = None) -> dict:
    kg = get_kg(session)
    evs = session.exec(select(Event).where(Event.event_date == day)).all()

    def in_scope(e):
        if discipline and (e.discipline or "") != discipline:
            return False
        if area:
            wf = e.location_zone_text or e.geofence_zone_id
            if not wf and e.matched_activity_id in kg.activities:
                wf = kg.activities[e.matched_activity_id].work_front
            w = kg.work_fronts.get(wf) if wf else None
            if not w or area not in (wf, w.unit, w.area):
                return False
        return True

    evs = [e for e in evs if in_scope(e) and e.state != "duplicate"]
    progress = defaultdict(list)
    for e in evs:
        if e.state in ("linked", "review", "clarifying") and not e.blocker_flag and (e.action or e.object_class):
            progress[e.matched_activity_id or (e.top_k_candidates[0]["activity_id"] if e.top_k_candidates else "—")].append(e)
    manpower = defaultdict(int)
    for e in evs:
        for t, n in (e.manpower_by_trade or {}).items():
            manpower[t] += n
    equipment = sorted({x for e in evs for x in (e.equipment_deployed or [])})
    blockers = [e for e in evs if e.blocker_flag]
    hse_ids = {e.id for e in evs}
    hse = [h for h in session.exec(select(HSEEvent)).all() if h.event_id in hse_ids]
    unplanned = [e for e in evs if e.state == "unplanned"]
    reps = {r.id: r.name for r in session.exec(select(Reporter))}
    acts = {a.activity_id: a for a in session.exec(select(Activity))}
    return {"day": day, "discipline": discipline, "area": area, "progress": progress, "manpower": dict(manpower),
            "equipment": equipment, "blockers": blockers, "hse": hse, "unplanned": unplanned, "reps": reps, "acts": acts, "n_events": len(evs)}


def _weather_line(e) -> str:
    if not (e.weather_reported or e.cause_category == "weather"):
        return ""
    wf = e.weather_fetched or {}
    return (f"reported: “{e.weather_reported or e.cause_subcategory or ''}” · fetched: {wf.get('rain_mm_window', wf.get('rain_mm', '—'))} mm "
            f"({e.weather_window or ''}; {e.weather_source or 'unavailable'}) · corroborated: {e.weather_corroborates or '—'}")


def render_html(d: dict) -> str:
    esc = html.escape
    day = d["day"].strftime("%d %b %Y")
    scope = " · ".join(x for x in [d["discipline"], d["area"]] if x) or "All disciplines, all areas"

    def table(head, body):
        empty = f"<tr><td colspan={len(head)} class=empty>None reported</td></tr>"
        return f"<table><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr>{''.join(body) or empty}</table>"

    rows = []
    for aid, evs in sorted(d["progress"].items(), key=lambda kv: str(kv[0])):
        a = d["acts"].get(aid)
        for e in evs:
            qty = "" if e.quantity is None else f"{e.quantity:g} {esc(e.uom or '')}"
            wrote = f" · <b>{esc(e.date_written.replace('actual_', 'Actual ').replace('+', ' & '))}</b>" if e.date_written else ""
            rows.append(f"<tr><td>{esc(aid)}</td><td>{esc(a.name if a else '')}</td><td>“{esc(e.source_sentence)}”</td><td>{qty}</td>"
                        f"<td>{esc(e.state)}{wrote}</td><td class=cite>EV-{e.id} · {esc(d['reps'].get(e.reporter_id, ''))} · {esc(e.channel or '')}</td></tr>")
    blk = [f"<tr><td>{esc(e.cause_category or '—')}</td><td>“{esc(e.cause_text or e.source_sentence)}”</td>"
           f"<td>{'' if e.time_lost_h is None else f'{e.time_lost_h:g} h'}</td><td>{esc(', '.join(e.affected_activities[:4]))}</td>"
           f"<td>{esc(_weather_line(e))}</td><td class=cite>EV-{e.id}</td></tr>" for e in d["blockers"]]
    hse = [f"<tr><td>{esc(h.kind)}</td><td>{esc(h.hse_event_type or '')}</td><td>{esc(h.hse_severity)}</td><td>“{esc(h.hse_event_text)}”</td>"
           f"<td>{esc(h.permit_type or '')} {esc(h.permit_status or '')}</td><td>{esc(h.status)}</td><td class=cite>EV-{h.event_id}</td></tr>" for h in d["hse"]]
    unp = [f"<tr><td>{esc(e.unplanned_class or '')}</td><td>“{esc(e.source_sentence)}”</td><td>{esc(e.suggested_parent_wbs or '')}</td>"
           f"<td class=cite>EV-{e.id}</td></tr>" for e in d["unplanned"]]
    mp = ", ".join(f"{t.replace('_', ' ')}: {n}" for t, n in sorted(d["manpower"].items())) or "—"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>DPR {day}</title>
<style>body{{font:13px/1.45 system-ui,Segoe UI,Arial;margin:32px;color:#111}}h1{{font-size:20px;margin:0}}
h2{{font-size:15px;margin:22px 0 6px;border-bottom:2px solid #0f766e;padding-bottom:3px}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #d4d4d8;padding:5px 7px;vertical-align:top;text-align:left}}th{{background:#f4f4f5}}
.cite{{font:11px ui-monospace,monospace;color:#0f766e;white-space:nowrap}}.meta{{color:#555}}.empty{{color:#888;font-style:italic}}
@media print{{body{{margin:12mm}}}}</style></head><body>
<h1>Daily Progress Report — reconstructed from field events</h1>
<div class=meta>RFX Assam · {day} · {esc(scope)} · {d['n_events']} source events · every line cites its source event</div>
<h2>1. Progress</h2>{table(['Activity', 'Name', 'Verbatim source', 'Qty', 'State / date written', 'Source'], rows)}
<h2>2. Manpower &amp; equipment</h2><p>{esc(mp)}</p><p>Equipment: {esc(', '.join(d['equipment']) or '—')}</p>
<h2>3. Blockers &amp; delay causes (verbatim)</h2>{table(['Cause', 'Verbatim text', 'Time lost', 'Affects', 'Weather: reported vs fetched', 'Source'], blk)}
<h2>4. HSE (verbatim — never paraphrased)</h2>{table(['Kind', 'Type', 'Severity', 'Verbatim', 'Permit', 'Status', 'Source'], hse)}
<h2>5. Unplanned work</h2>{table(['Class', 'Verbatim', 'Suggested parent WBS', 'Source'], unp)}
<p class=meta style="margin-top:24px">Generated by SiteSync from the event store. Provenance and spans for every cited event are in the Event Explorer.</p>
</body></html>"""


def render_pdf(d: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=7.5, leading=9)

    def P(t):
        return Paragraph(html.escape(str(t)), small)

    story = [Paragraph(f"Daily Progress Report — {d['day']:%d %b %Y} — reconstructed from field events", ss["Title"]),
             Paragraph(f"{d['n_events']} source events · every line cites its source event", ss["Normal"]), Spacer(1, 8)]

    def tbl(title, head, rows, widths):
        story.append(Paragraph(title, ss["Heading3"]))
        data = [[P(h) for h in head]] + ([[P(c) for c in r] for r in rows] or [[P("None reported")] + [P("")] * (len(head) - 1)])
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)

    prog = [(aid, d["acts"][aid].name if aid in d["acts"] else "", f"“{e.source_sentence}”", "" if e.quantity is None else f"{e.quantity:g} {e.uom or ''}",
             e.state + (f" · {e.date_written}" if e.date_written else ""), f"EV-{e.id}")
            for aid, evs in sorted(d["progress"].items(), key=lambda kv: str(kv[0])) for e in evs]
    tbl("1. Progress", ["Activity", "Name", "Verbatim source", "Qty", "State / write", "Source"], prog, [60, 150, 280, 50, 120, 50])
    story.append(Paragraph("2. Manpower: " + html.escape(", ".join(f"{t}: {n}" for t, n in sorted(d["manpower"].items())) or "—"), ss["Normal"]))
    blk = [(e.cause_category or "—", f"“{e.cause_text or e.source_sentence}”", "" if e.time_lost_h is None else f"{e.time_lost_h:g} h",
            ", ".join(e.affected_activities[:3]), _weather_line(e), f"EV-{e.id}") for e in d["blockers"]]
    tbl("3. Blockers (verbatim)", ["Cause", "Verbatim", "Lost", "Affects", "Weather", "Source"], blk, [60, 230, 40, 120, 220, 50])
    hs = [(h.kind, h.hse_event_type or "", h.hse_severity, f"“{h.hse_event_text}”", f"{h.permit_type or ''} {h.permit_status or ''}", h.status,
           f"EV-{h.event_id}") for h in d["hse"]]
    tbl("4. HSE (verbatim)", ["Kind", "Type", "Severity", "Verbatim", "Permit", "Status", "Source"], hs, [50, 70, 55, 300, 90, 60, 50])
    unp = [(e.unplanned_class or "", f"“{e.source_sentence}”", e.suggested_parent_wbs or "", f"EV-{e.id}") for e in d["unplanned"]]
    tbl("5. Unplanned work", ["Class", "Verbatim", "Suggested parent WBS", "Source"], unp, [80, 400, 150, 60])
    doc.build(story)
    return buf.getvalue()
