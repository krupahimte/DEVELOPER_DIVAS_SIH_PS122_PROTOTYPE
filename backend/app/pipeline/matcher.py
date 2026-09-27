"""KG + semantic/fuzzy matcher (spec §4.5).

Tier 1 kg_narrowed   candidates = open activities reachable in the KG from the event's
                     seeds (GPS zone, text zone/aliases, reporter work fronts, objects,
                     lines, drawings), filtered by the active look-ahead window and
                     predecessor eligibility (explicitly identified objects bypass the
                     filters but raise a contradiction instead).
Tier 2 vector_only   TF-IDF (or MiniLM when USE_MINILM=1) over open activities.
Tier 3 fuzzy_fallback rapidfuzz token-set ratio over open activities.

Every candidate is scored by *compatibility* with what the report states — additive
signals and mismatch penalties, capped at 0.99. Scores are per-candidate (not
normalised across candidates), which is exactly why `match_margin` matters: two
candidates at .91/.87 both fit, and the gate must not pretend otherwise.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlmodel import Session

from .. import config
from ..models import Activity, Event, MaterialIssue, Report, Reporter
from .kg import KG, norm

W = {  # signal weights
    "object_id": 0.35, "alias": 0.10, "line_exact": 0.30, "line_partial": 0.20, "line_via_object": 0.15, "drawing": 0.25,
    "text_location": 0.20, "location_partial": 0.05, "unit": 0.05, "geofence": 0.15, "reporter_scope": 0.12,
    "action": 0.25, "action_related": 0.10, "object_class": 0.15, "object_class_related": 0.05, "discipline": 0.05,
    "lookahead": 0.05, "in_progress": 0.05, "prior_event": 0.15, "reporter_confirmed": 0.30, "fuzzy": 0.15,
}
P = {  # penalties
    "object_mismatch": -0.25, "line_mismatch": -0.30, "line_partial_mismatch": -0.20, "location_mismatch": -0.25,
    "unit_mismatch": -0.20, "geofence_mismatch": -0.10, "action_mismatch": -0.15, "object_class_mismatch": -0.20,
    "discipline_mismatch": -0.10, "reporter_scope_mismatch": -0.15,
}
RELATED_ACTIONS = [{"erect", "install", "fit_up"}, {"pour", "rebar", "shutter"}, {"test", "flush"}, {"weld", "fit_up"}, {"lay", "pull"}]
CLASS_FAMILIES = [{"spool", "joint", "line", "support"}, {"foundation", "pedestal", "ring wall", "tank pad", "basin"},
                  {"cable", "tray", "earthing"}, {"loop", "instrument", "transmitter", "tubing"}, {"steel", "girder", "bolt", "grating"},
                  {"pump", "compressor"}]
CONTINUE_RX = re.compile(r"\b(continu\w*|same|jari|again|phir\s+se|ongoing|chal\s+raha)\b", re.I)


def _related(a, b, families):
    return any(a in f and b in f for f in families)


@dataclass
class Ctx:
    """Everything the scorer knows about the event."""
    text: str
    action: str | None
    object_class: str | None
    event_type: str | None
    ordinals: list
    objects: set = field(default_factory=set)             # resolved object ids
    objects_explicit: bool = False
    obj_lines: set = field(default_factory=set)
    line_full: str | None = None
    line_partial: str | None = None
    drawing_line: str | None = None
    text_zones: set = field(default_factory=set)
    units: set = field(default_factory=set)
    gps_zone: str | None = None
    nearby_zones: set = field(default_factory=set)
    rep_fronts: set = field(default_factory=set)
    rep_discipline: str | None = None
    alias_acts: set = field(default_factory=set)
    alias_hits: list = field(default_factory=list)
    prior_acts: set = field(default_factory=set)
    confirmed: str | None = None
    location_tokens: set = field(default_factory=set)


def is_open(a: Activity) -> bool:
    return a.actual_finish is None


def in_lookahead(a: Activity, today: date, settings: dict) -> bool:
    if a.actual_start and not a.actual_finish:
        return True
    ahead = settings.get("lookahead_days_ahead", 14)
    behind = settings.get("lookahead_days_behind", 60)
    return a.planned_start <= today + timedelta(days=ahead) and a.planned_finish >= today - timedelta(days=behind)


def preds_done(kg: KG, a: Activity) -> list[str]:
    """→ list of predecessors that are NOT finished."""
    return [p for p in a.predecessors or [] if p in kg.activities and kg.activities[p].actual_finish is None]


def build_ctx(kg: KG, ev: Event, reporter: Reporter | None, prior_acts: set, confirmed: str | None) -> Ctx:
    text = ev.source_sentence or ""
    c = Ctx(text=norm(text), action=ev.action, object_class=ev.object_class, event_type=ev.object_event_type,
            ordinals=list(ev.object_ordinals or []), confirmed=confirmed)
    if reporter:
        c.rep_fronts = set(reporter.work_fronts or [])
    context_zones = set(c.rep_fronts) | ({ev.geofence_zone_id} if ev.geofence_zone_id else set()) \
        | set((ev.field_conf or {}).get("_nearby_zones", []))
    # aliases (seeded names + learned terms) — spans relative to the sentence
    for h in kg.find_aliases(text):
        scope = kg.alias_scope.get((h.term, h.target))
        if scope and scope not in context_zones:
            continue            # zone-scoped alias (e.g. "spool 5" means something only on Rack B)
        c.alias_hits.append(h)
        if h.target_type == "work_front":
            c.text_zones.add(h.target)
        elif h.target_type == "line":
            if not ev.line_ref or "-" not in (ev.line_ref or ""):
                c.line_full = c.line_full or h.target
        elif h.target_type == "object":
            c.objects.add(h.target)
            c.objects_explicit = True
        elif h.target_type == "activity":
            c.alias_acts.add(h.target)
    # DPR section heading ("UNIT 3 - TANK FARM") is location context for every line under it
    if ev.document_section:
        for h in kg.find_aliases(ev.document_section):
            if h.target_type == "work_front":
                c.text_zones.add(h.target)
    # explicit ids from text
    if ev.line_ref:
        if "-" in ev.line_ref:
            c.line_full = ev.line_ref
        else:
            c.line_partial = ev.line_ref
    if ev.drawing_no:
        c.drawing_line = next((l.line_no for l in kg.lines.values() if l.drawing_no == ev.drawing_no), None)
    for ref in ev.object_ids or []:
        c.objects.add(ref)
        c.objects_explicit = True
    for u in re.findall(r"\b(?:unit|u)\s*-?\s*([23])\b", text, re.I):
        c.units.add(f"Unit {u}")
    loc = norm(ev.location_text or "")
    c.location_tokens = {t for t in loc.split() if t not in {"near", "at", "the", "unit", "inside"} and len(t) > 2}
    if ev.geofence_result == "inside":
        c.gps_zone = ev.geofence_zone_id
    c.nearby_zones = set((ev.field_conf or {}).get("_nearby_zones", []))
    if reporter:
        c.rep_discipline = reporter.discipline
    if CONTINUE_RX.search(text) or (not ev.object_ordinals and not ev.object_ids and not ev.location_text and ev.action):
        c.prior_acts = prior_acts
    return c


def resolve_objects(kg: KG, c: Ctx, candidates: list[str]):
    """Turn ordinals ("spool 3 aur 4") into object ids using the candidate activities' scope.
    Learned object aliases override ordinal resolution."""
    if c.objects_explicit or not c.ordinals:
        c.obj_lines = {kg.line_of_object(o) for o in c.objects if kg.line_of_object(o)}
        return
    def collect(zones):
        found = set()
        for aid in candidates:
            a = kg.activities[aid]
            if c.object_class and a.object_class and c.object_class != a.object_class:
                continue
            for so in a.scope_objects or []:
                o = kg.objects.get(so)
                if o and o.ordinal in c.ordinals and (not zones or o.work_front in zones or a.work_front in zones):
                    found.add(so)
        return found

    # text location is a hard restriction; GPS is only a preference (fall back to all candidates)
    if c.text_zones:
        c.objects |= collect(c.text_zones)
    else:
        gz = ({c.gps_zone} if c.gps_zone else set()) or c.nearby_zones
        c.objects |= (collect(gz) if gz else set()) or collect(set())
    c.obj_lines = {kg.line_of_object(o) for o in c.objects if kg.line_of_object(o)}


def score(kg: KG, a: Activity, c: Ctx, today: date, settings: dict):
    s, sig, pen = 0.0, [], []

    def add(name, w=None):
        nonlocal s
        s += W[name] if w is None else w
        sig.append(name)

    def sub(name):
        nonlocal s
        s += P[name]
        pen.append(name)

    scope = set(a.scope_objects or [])
    if c.objects:
        if scope & c.objects:
            add("object_id")
            if any(h.target_type == "object" and h.target in scope for h in c.alias_hits):
                add("alias")
        elif scope and (not c.object_class or not a.object_class or c.object_class == a.object_class
                        or _related(c.object_class, a.object_class, CLASS_FAMILIES)):
            sub("object_mismatch")
    elif c.ordinals and scope and (not c.object_class or c.object_class == a.object_class):
        # "spool 4" said, but this activity's spools are 5–6
        ords = {kg.objects[so].ordinal for so in scope if so in kg.objects and kg.objects[so].ordinal is not None}
        if ords and not (ords & set(c.ordinals)):
            sub("object_mismatch")
    if a.activity_id in c.alias_acts:
        add("alias", 0.35)
    if c.line_full and a.line_no:
        add("line_exact") if a.line_no == c.line_full else sub("line_mismatch")
    elif c.line_partial and a.line_no:
        add("line_partial") if a.line_no.split("-")[0] == c.line_partial else sub("line_partial_mismatch")
    if a.line_no and a.line_no in c.obj_lines and "line_exact" not in sig:
        add("line_via_object")
    if c.drawing_line and a.line_no == c.drawing_line:
        add("drawing")
    if c.text_zones and a.work_front:
        if a.work_front in c.text_zones:
            add("text_location")
            if any(h.learned and h.target_type == "work_front" and h.target == a.work_front for h in c.alias_hits):
                add("alias")
        else:
            sub("location_mismatch")
    elif c.location_tokens and a.work_front:
        wf_tokens = set(norm(kg.work_fronts[a.work_front].name).split())
        if c.location_tokens & wf_tokens:
            add("location_partial")
    if c.units:
        add("unit") if a.unit in c.units else sub("unit_mismatch")
    if a.work_front:
        if c.gps_zone:
            if a.work_front == c.gps_zone:
                add("geofence")
            elif not c.text_zones:
                sub("geofence_mismatch")
        if a.work_front in c.rep_fronts:
            add("reporter_scope")
        elif c.rep_fronts and not c.gps_zone and not c.text_zones and not c.nearby_zones:
            sub("reporter_scope_mismatch")      # no location evidence at all, and not the reporter's own front
    if c.action and a.action:
        if c.action == a.action:
            add("action")
        elif _related(c.action, a.action, RELATED_ACTIONS):
            add("action_related")
        else:
            sub("action_mismatch")
    if c.object_class and a.object_class:
        if c.object_class == a.object_class:
            add("object_class")
        elif _related(c.object_class, a.object_class, CLASS_FAMILIES):
            add("object_class_related")
        else:
            sub("object_class_mismatch")
    if c.rep_discipline:
        add("discipline") if c.rep_discipline == a.discipline else sub("discipline_mismatch")
    if in_lookahead(a, today, settings) and a.planned_start <= today + timedelta(days=settings.get("lookahead_days_ahead", 14)):
        add("lookahead")
    if a.actual_start and not a.actual_finish:
        add("in_progress")
    if a.activity_id in c.prior_acts:
        add("prior_event")
    if c.confirmed == a.activity_id:
        add("reporter_confirmed")
    fz = fuzz.token_set_ratio(c.text, norm(a.name)) / 100.0
    s += W["fuzzy"] * fz
    if fz >= 0.6:
        sig.append("name_similarity")
    return max(0.0, min(0.99, s)), sig, pen, fz


def _kg_seeds(kg: KG, c: Ctx) -> tuple[set, bool]:
    """Candidate activity ids reachable from the event's seeds. Returns (ids, explicit_ids)."""
    ids, explicit = set(), set()
    for z in c.text_zones | ({c.gps_zone} if c.gps_zone else set()) | c.nearby_zones | c.rep_fronts:
        ids |= set(kg.activities_at(z))
    for u in c.units:
        for z in kg.work_fronts_in_unit(u):
            ids |= set(kg.activities_at(z))
    for o in c.objects:
        e = set(kg.activities_for_object(o))
        ids |= e
        if c.objects_explicit:
            explicit |= e
    for ln in filter(None, [c.line_full, c.drawing_line]):
        e = set(kg.activities_for_line(ln))
        ids |= e
        explicit |= e
    if c.line_partial:
        for ln in kg.lines_for_partial(c.line_partial):
            ids |= set(kg.activities_for_line(ln))
    ids |= c.alias_acts
    explicit |= c.alias_acts
    if c.confirmed:
        ids.add(c.confirmed)
        explicit.add(c.confirmed)
    return ids, explicit


_vec_cache = {}


def _vector_rank(kg: KG, pool: list[str], text: str, k=8) -> list[str]:
    if not pool:
        return []
    if config.USE_MINILM:
        try:
            from sentence_transformers import SentenceTransformer, util  # optional upgrade
            model = _vec_cache.setdefault("minilm", SentenceTransformer("all-MiniLM-L6-v2"))
            docs = [_doc(kg, a) for a in pool]
            sims = util.cos_sim(model.encode([text]), model.encode(docs))[0].tolist()
            return [pool[i] for i in sorted(range(len(pool)), key=lambda i: -sims[i])[:k]]
        except Exception:
            pass
    key = (kg.version, tuple(pool))
    if key not in _vec_cache:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), sublinear_tf=True)
        _vec_cache[key] = (vec, vec.fit_transform([_doc(kg, a) for a in pool]))
    vec, mat = _vec_cache[key]
    sims = cosine_similarity(vec.transform([text]), mat)[0]
    order = sims.argsort()[::-1][:k]
    return [pool[i] for i in order if sims[i] > 0.05]


def _doc(kg: KG, aid: str) -> str:
    a = kg.activities[aid]
    wf = kg.work_fronts.get(a.work_front)
    line = kg.lines.get(a.line_no) if a.line_no else None
    return norm(" ".join(filter(None, [a.name, wf.name if wf else "", a.unit, a.discipline, line.system if line else "", line.drawing_no if line else ""])))


def match(session: Session, kg: KG, ev: Event, reporter: Reporter | None, today: date, settings: dict,
          prior_acts: set = frozenset(), confirmed: str | None = None) -> dict:
    kg.refresh_dynamic(session)
    c = build_ctx(kg, ev, reporter, set(prior_acts), confirmed)
    cand_min = settings["gate"]["candidate_min"]

    def rank(ids, explicit, allow_pred_open=False):
        out = []
        for aid in ids:
            a = kg.activities.get(aid)
            if not a or not is_open(a):
                continue
            eligible = in_lookahead(a, today, settings) and (allow_pred_open or not preds_done(kg, a))
            if not eligible and aid not in explicit:
                continue
            sc, sig, pen, fz = score(kg, a, c, today, settings)
            out.append((sc, aid, sig, pen))
        out.sort(key=lambda x: (-x[0], x[1]))
        return out

    open_pool = [aid for aid, a in kg.activities.items() if is_open(a) and in_lookahead(a, today, settings)]
    seeds, explicit = _kg_seeds(kg, c)
    eligible_seeds = [s for s in seeds if s in kg.activities and is_open(kg.activities[s])
                      and ((in_lookahead(kg.activities[s], today, settings) and not preds_done(kg, kg.activities[s])) or s in explicit)]
    resolve_objects(kg, c, eligible_seeds)
    seeds2, explicit2 = _kg_seeds(kg, c)       # objects may add seeds
    seeds |= seeds2
    explicit |= explicit2

    path, ranked, cset = None, [], 0
    if seeds:
        ranked = rank(seeds, explicit)
        if not ranked or ranked[0][0] < cand_min:
            # the plan may lag the site: let predecessor-open activities compete (they get a contradiction flag)
            relaxed = rank(seeds, explicit, allow_pred_open=True)
            if relaxed and (not ranked or relaxed[0][0] > ranked[0][0]):
                ranked = relaxed
        path, cset = "kg_narrowed", len(ranked)
    if not ranked or ranked[0][0] < cand_min:
        pool = [a for a in open_pool if not c.rep_discipline or kg.activities[a].discipline == c.rep_discipline] or open_pool
        vr = rank(_vector_rank(kg, pool, c.text), explicit)
        if vr and vr[0][0] >= cand_min and (not ranked or vr[0][0] > ranked[0][0]):
            ranked, path, cset = vr, "vector_only", len(pool)
        elif not ranked or ranked[0][0] < cand_min:
            fz = sorted(open_pool, key=lambda a: -fuzz.token_set_ratio(c.text, norm(kg.activities[a].name)))[:8]
            fr = rank(fz, explicit)
            if fr and (not ranked or fr[0][0] > ranked[0][0]):
                ranked, path, cset = fr, "fuzzy_fallback", len(open_pool)
    if path is None:
        path = "fuzzy_fallback"

    seed_node = _best_seed(kg, c, reporter)
    top = []
    for sc, aid, sig, pen in ranked[:3]:
        a = kg.activities[aid]
        top.append({
            "activity_id": aid, "name": a.name, "score": round(sc, 3), "signals": sig, "penalties": pen,
            "work_front": a.work_front, "wf_name": kg.work_fronts[a.work_front].name if a.work_front else None,
            "line_no": a.line_no, "planned_start": a.planned_start.isoformat(), "planned_finish": a.planned_finish.isoformat(),
            "actual_start": a.actual_start.isoformat() if a.actual_start else None, "discipline": a.discipline,
            "kg_path": kg.path(seed_node, aid) if seed_node else [],
            "explicit": aid in explicit,
        })
    margin = round(top[0]["score"] - top[1]["score"], 3) if len(top) >= 2 else (round(top[0]["score"], 3) if top else None)

    # ── cross-checks on the top candidate (never reject — lower conf + flag) ──
    contradictions, match_conf, material = [], (top[0]["score"] if top else 0.0), None
    if top:
        a = kg.activities[top[0]["activity_id"]]
        open_preds = preds_done(kg, a)
        if open_preds and ev.object_event_type != "none":
            contradictions.append(f"predecessor_open:{','.join(open_preds)}")
            match_conf -= 0.15
        mats = [o for o in c.objects if o in set(a.scope_objects or [])] or sorted(c.objects)
        for m_id in mats:
            mi = session.get(MaterialIssue, m_id)
            if mi:
                material = {"item": m_id, "status": mi.status}
                if mi.status == "not_issued":
                    contradictions.append(f"material_not_issued:{m_id}")
                    break
        if not in_lookahead(a, today, settings):
            top[0]["signals"] = top[0]["signals"] + ["outside_lookahead"]

    rationale = _rationale(top, path, cset, c)
    return {
        "path": path, "candidate_set_size": cset, "top": top, "margin": margin, "match_conf": round(max(0.0, match_conf), 3),
        "contradictions": contradictions, "material": material, "resolved_objects": sorted(c.objects),
        "text_zones": sorted(c.text_zones), "alias_hits": [(h.term, h.target, h.learned) for h in c.alias_hits], "rationale": rationale,
    }


def _best_seed(kg: KG, c: Ctx, reporter):
    for o in sorted(c.objects):
        if f"obj:{o}" in kg.g:
            return f"obj:{o}"
    for h in c.alias_hits:
        if h.learned:
            return f"alias:{h.term}" if f"alias:{h.term}" in kg.g else None
    if c.line_full:
        return f"line:{c.line_full}"
    if c.text_zones:
        return f"wf:{sorted(c.text_zones)[0]}"
    if c.gps_zone:
        return f"wf:{c.gps_zone}"
    if reporter:
        return f"rep:{reporter.id}"
    return None


def _rationale(top, path, cset, c: Ctx) -> str:
    if not top:
        return f"No candidate found ({path}, searched {cset})."
    t = top[0]
    parts = [f"{t['activity_id']} scored {t['score']:.2f} via {path} (candidate set {cset})."]
    if t["signals"]:
        parts.append("Signals: " + ", ".join(t["signals"]) + ".")
    if t["penalties"]:
        parts.append("Penalties: " + ", ".join(t["penalties"]) + ".")
    if len(top) > 1:
        parts.append(f"Runner-up {top[1]['activity_id']} at {top[1]['score']:.2f} (margin {t['score'] - top[1]['score']:.2f}).")
    return " ".join(parts)
