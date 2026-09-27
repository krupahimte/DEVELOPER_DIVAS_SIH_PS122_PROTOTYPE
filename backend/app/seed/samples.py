"""Generate /sample_data demo inputs: photos (with/without/old EXIF), a DPR PDF, a messy
xlsx DPR with non-standard headers, and a Hinglish WhatsApp chat export."""
import json
from datetime import datetime
from fractions import Fraction

from PIL import Image, ImageDraw

from .. import config

PHOTOS = config.SAMPLE_DIR / "photos"


def _dms(x: float):
    d = int(x)
    m = int((x - d) * 60)
    s = round(((x - d) * 60 - m) * 60, 2)
    return (Fraction(d), Fraction(m), Fraction(s).limit_denominator(100))


def _photo(name, label, color, lat=None, lon=None, when: datetime | None = None):
    im = Image.new("RGB", (640, 480), color)
    dr = ImageDraw.Draw(im)
    for i in range(0, 640, 40):
        dr.line([(i, 300), (i + 60, 480)], fill=(90, 90, 90), width=3)
    dr.rectangle([60, 140, 580, 230], fill=(120, 120, 130))
    dr.text((70, 40), label, fill=(255, 255, 255))
    dr.text((70, 440), f"SiteSync sample · {name}", fill=(255, 255, 255))
    exif = Image.Exif()
    if when:
        exif[0x0132] = when.strftime("%Y:%m:%d %H:%M:%S")
        exif.get_ifd(0x8769)[36867] = when.strftime("%Y:%m:%d %H:%M:%S")
    if lat is not None:
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2], gps[3], gps[4] = "N", _dms(lat), "E", _dms(lon)
    im.save(PHOTOS / name, "JPEG", exif=exif.tobytes() if (when or lat) else b"")


def write_samples():
    PHOTOS.mkdir(parents=True, exist_ok=True)
    today = datetime.fromisoformat(config.PROJECT_TODAY + "T14:05:00")
    _photo("spool_erection_rackB.jpg", "Spool erection - Rack B", (70, 90, 120), 27.47432, 95.33752, today)
    _photo("hydrotest_line24_gauge.jpg", "Hydrotest gauge - line 24-P-1108", (60, 110, 90), 27.47521, 95.33774, today)
    _photo("site_photo_no_exif.jpg", "Photo with stripped EXIF (WhatsApp)", (110, 80, 70))
    _photo("spool_rackB_old.jpg", "Old photo (EXIF 2 months back)", (90, 90, 60), 27.47433, 95.33751, datetime(2026, 7, 24, 11, 20))
    (PHOTOS / "cv_lookup.json").write_text(json.dumps({
        "spool_erection_rackb.jpg": ["pipe_section", "flange", "steel_structure", "crane", "worker"],
        "hydrotest_line24_gauge.jpg": ["pressure_gauge", "pipe_section", "hose", "worker"],
        "site_photo_no_exif.jpg": ["worker", "site_background"],
        "spool_rackb_old.jpg": ["pipe_section", "steel_structure"],
    }, indent=1))
    _chat_export()
    _xlsx()
    _pdf()


def _chat_export():
    lines = [
        "[26/09/26, 8:02 AM] S. Kalita: Good morning sir, aaj Rack B pe 10 fitter 6 welder",
        "[26/09/26, 11:40 AM] M. Bora: Line 24 hydrotest pressure hold chal raha hai, 2 ghante",
        "[26/09/26, 1:15 PM] R. Gogoi: F-13 shuttering complete ho gaya, 6 carpenter",
        "[26/09/26, 3:30 PM] T. Konwar: Rack A pe steam line spool 5 erect kiya",
        "[26/09/26, 4:05 PM] A. Sharma: Cable pulling tray T-6 shuru, 8 helper",
    ]
    (config.SAMPLE_DIR / "whatsapp_chat_export_hinglish.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _xlsx():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "DPR 25-Sep"
    ws.append(["NE Electricals & Instruments / Brahmaputra Civil Works — Daily Progress Report"])
    ws.append(["Project: RFX Assam", "", "Date: 25/09/2026"])
    ws.append([])
    ws.append(["Sl", "Desc of Work", "Area / Locn", "Qty Done", "Nos", "Manpwr", "Remarks"])
    rows = [
        (1, "Cable pulling tray T-5", "Unit 2 Rack A", 180, "m", 10, "continued"),
        (2, "Cable tray installation tray T-6", "Unit 2 Rack A", 24, "m", 6, "in progress"),
        (3, "LT panel erection", "SS-2", 2, "nos", 5, "completed"),
        (4, "Cable termination HT panel", "SS-2", 12, "nos", 4, "started"),
        (5, "Loop check L-305", "Pump House", 1, "nos", 2, "done"),
        (6, "Impulse tubing", "Pump House", 30, "m", 3, "in progress"),
        (7, "Excavation F-14", "Unit 3 Fdn area", 45, "m3", 8, "started"),
        (8, "Reinforcement F-13", "Unit 3 Fdn area", 1.2, "MT", 6, "in progress"),
        (9, "Basin wall waterproofing", "Cooling Tower", 40, "sqm", 5, "started"),
        (10, "Tank pad sand filling", "Tank Farm", 60, "m3", 7, "completed"),
        (11, "Motor cabling P-101A/B", "Pump House", 90, "m", 4, "in progress"),
        (12, "Instrument cable tray", "Rack C", 18, "m", 3, "continued"),
    ]
    for r in rows:
        ws.append(list(r))
    wb.save(config.SAMPLE_DIR / "dpr_25sep_messy_headers.xlsx")


def _pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(config.SAMPLE_DIR / "dpr_piping_24sep.pdf"), pagesize=A4)
    y = 800
    lines = [
        ("h", "L&T Hydrocarbon — Daily Progress Report (Piping)"), ("t", "Project: RFX Assam   Date: 24-Sep-2026   Reporter: M. Bora"),
        ("t", ""), ("h", "UNIT 3 - TANK FARM"),
        ("t", "Hydrotest line 24-P-1108 started, filling in progress, 6 fitter 2 helper."),
        ("t", "Welding machine WM-02 breakdown at tank farm, 2 hrs lost."),
        ("h", "UNIT 3 - PUMP HOUSE"),
        ("t", "Erect spools line 10-P-1301 continued, spool 2 erected, 4 fitter."),
        ("h", "UNIT 3 - RACK C"),
        ("t", "Spool 5 for Rack C not received from fab yard."),
        ("h", "HSE"),
        ("t", "Toolbox talk on working at height conducted, 42 persons."),
    ]
    for kind, txt in lines:
        c.setFont("Helvetica-Bold" if kind == "h" else "Helvetica", 12 if kind == "h" else 10)
        c.drawString(50, y, txt)
        y -= 20
    c.save()
