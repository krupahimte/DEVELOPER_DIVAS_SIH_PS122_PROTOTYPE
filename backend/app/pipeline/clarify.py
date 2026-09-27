"""Clarifying agent — ONE short multiple-choice question, never more (spec §4.7).

The question is built from whatever distinguishes the top-2 candidates (work front,
line, object scope), or from the single borderline dimension (photo / date / reading).
The cap is enforced per report by the caller.
"""
from datetime import timedelta


def _fmt(d):
    return d.strftime("%d-%b")


def build(dimension: str, top: list, ev, kg) -> dict:
    """→ {question, question_hi, options:[{label,label_hi,value}]}"""
    if dimension in ("margin", "match") and len(top) >= 2:
        a, b = top[0], top[1]
        if a.get("wf_name") and b.get("wf_name") and a["wf_name"] != b["wf_name"]:
            la, lb = a["wf_name"], b["wf_name"]
        elif a.get("line_no") and b.get("line_no") and a["line_no"] != b["line_no"]:
            la, lb = f"Line {a['line_no']}", f"Line {b['line_no']}"
        else:
            la, lb = a["name"], b["name"]
        return {"question": f"{la} or {lb}?", "question_hi": f"{la} या {lb}?",
                "options": [{"label": la, "label_hi": la, "value": a["activity_id"]},
                            {"label": lb, "label_hi": lb, "value": b["activity_id"]},
                            {"label": "Something else", "label_hi": "कुछ और", "value": "__other"}]}
    if dimension == "verification":
        return {"question": "Can you send one photo of this work?", "question_hi": "क्या आप इस काम की एक फ़ोटो भेज सकते हैं?",
                "options": [{"label": "📷 Send photo", "label_hi": "📷 फ़ोटो भेजें", "value": "__photo"},
                            {"label": "No photo", "label_hi": "फ़ोटो नहीं", "value": "__nophoto"}]}
    if dimension == "date":
        d = ev.event_date
        return {"question": "When was this done?", "question_hi": "यह काम कब हुआ?",
                "options": [{"label": f"Today ({_fmt(d)})", "label_hi": f"आज ({_fmt(d)})", "value": f"date:{d.isoformat()}"},
                            {"label": f"Yesterday ({_fmt(d - timedelta(days=1))})", "label_hi": f"कल ({_fmt(d - timedelta(days=1))})",
                             "value": f"date:{(d - timedelta(days=1)).isoformat()}"}]}
    # extraction: echo back what we understood
    echo = plain_echo(ev, None)
    return {"question": f"Did you mean: {echo}?", "question_hi": f"क्या आपका मतलब है: {echo}?",
            "options": [{"label": "✅ Yes", "label_hi": "✅ हाँ", "value": "__yes"}, {"label": "✏️ No", "label_hi": "✏️ नहीं", "value": "__no"}]}


def plain_echo(ev, wf_name) -> str:
    """Plain words, no jargon — what the worker sees."""
    bits = []
    if ev.object_qualifier:
        bits.append(ev.object_qualifier.replace(" aur ", " & ").replace(" and ", " & "))
    elif ev.line_ref:
        bits.append(f"Line {ev.line_ref}")
    elif ev.object_class:
        bits.append(ev.object_class)
    done = {"erect": "erected", "weld": "welded", "pour": "concreted", "excavate": "excavated", "pull": "pulled", "test": "test done",
            "install": "installed", "lay": "laid", "paint": "painted", "align": "aligned", "grout": "grouted", "rebar": "rebar done",
            "shutter": "shuttering done", "backfill": "backfilled", "terminate": "terminated", "calibrate": "calibrated"}
    noun = {"weld": "welding", "pour": "concreting", "excavate": "excavation", "pull": "cable pulling", "test": "test", "paint": "painting",
            "align": "alignment", "rebar": "rebar", "shutter": "shuttering", "erect": "erection", "install": "installation", "lay": "laying"}
    a = ev.action or ""
    if a:
        if ev.object_event_type == "finish":
            bits.append(done.get(a, a))
        elif ev.object_event_type == "start":
            bits.append(f"{noun.get(a, a)} started")
        else:
            bits.append(f"{noun.get(a, a)} in progress")
    if wf_name or ev.location_text:
        bits.append(wf_name or ev.location_text)
    out = ", ".join(b for b in bits if b).strip()
    return (out[:1].upper() + out[1:]) if out else (ev.source_sentence or "")[:60]
