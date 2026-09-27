"""Knowledge graph (networkx) of the plan-side context the report text never states.

Nodes (prefix:type)
  act:  Activity          wf:  WorkFront       area: Area         unit: Unit
  obj:  Object (spool/fdn/tray/loop/tag)       line: Line/object   dwg: Drawing
  sys:  System            rep: Reporter        con: Contractor     pkg: ScopePackage
  alias: Alias (seeded names + planner-learned terms)

Edges (schema-v2 "KG context edges")
  obj→line (part_of) · line→dwg (object→drawing_no) · line→sys (object→system)
  wf→area→unit · rep→wf · act→pred · con→pkg · act→wf · act→obj · act→line · alias→target

The graph is structural; dynamic activity state (actual dates) is read from the DB.
It is rebuilt lazily when `invalidate()` is called (e.g. a new alias was learned).
"""
import re
from dataclasses import dataclass, field

import networkx as nx
from sqlmodel import Session, select

from ..models import Activity, Alias, Contractor, Line, ObjectItem, Reporter, WorkFront

_cache: "KG | None" = None
_version = 0


def invalidate():
    global _cache, _version
    _cache = None
    _version += 1


def get_kg(session: Session) -> "KG":
    global _cache
    if _cache is None:
        _cache = KG.build(session)
    return _cache


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\- ]", " ", (s or "").lower())).strip()


@dataclass
class AliasHit:
    term: str
    span: tuple[int, int]
    target_type: str          # work_front | line | object | activity | unit
    target: str
    learned: bool


@dataclass
class KG:
    g: nx.Graph
    activities: dict
    work_fronts: dict
    lines: dict
    objects: dict
    reporters: dict
    contractors: dict
    aliases: list = field(default_factory=list)    # [(term, target_type, target, learned)] longest first
    version: int = 0
    alias_scope: dict = field(default_factory=dict)  # (term, target) → scope work front

    @classmethod
    def build(cls, session: Session) -> "KG":
        g = nx.Graph()
        # transient snapshots: safe to keep across sessions/commits (dynamic dates refreshed per match)
        snap = lambda cls, rows: [cls(**r.model_dump()) for r in rows]  # noqa: E731
        acts = {a.activity_id: a for a in snap(Activity, session.exec(select(Activity)))}
        wfs = {w.id: w for w in snap(WorkFront, session.exec(select(WorkFront)))}
        lines = {l.line_no: l for l in snap(Line, session.exec(select(Line)))}
        objs = {o.object_id: o for o in snap(ObjectItem, session.exec(select(ObjectItem)))}
        reps = {r.id: r for r in snap(Reporter, session.exec(select(Reporter)))}
        cons = {c.id: c for c in snap(Contractor, session.exec(select(Contractor)))}

        for u in {w.unit for w in wfs.values()}:
            g.add_node(f"unit:{u}", kind="unit", label=u)
        for w in wfs.values():
            g.add_node(f"wf:{w.id}", kind="work_front", label=w.name)
            area = f"area:{w.unit}/{w.area}"
            g.add_node(area, kind="area", label=w.area)
            g.add_edge(f"wf:{w.id}", area, rel="in_area")
            g.add_edge(area, f"unit:{w.unit}", rel="in_unit")
        for l in lines.values():
            g.add_node(f"line:{l.line_no}", kind="line", label=l.line_no)
            g.add_node(f"dwg:{l.drawing_no}", kind="drawing", label=l.drawing_no)
            g.add_node(f"sys:{l.system}", kind="system", label=l.system)
            g.add_edge(f"line:{l.line_no}", f"dwg:{l.drawing_no}", rel="drawing")
            g.add_edge(f"line:{l.line_no}", f"sys:{l.system}", rel="system")
        for o in objs.values():
            g.add_node(f"obj:{o.object_id}", kind="object", label=o.label or o.object_id)
            if o.parent and f"line:{o.parent}" in g:
                g.add_edge(f"obj:{o.object_id}", f"line:{o.parent}", rel="part_of")
            if o.work_front:
                g.add_edge(f"obj:{o.object_id}", f"wf:{o.work_front}", rel="located_at")
        for c in cons.values():
            g.add_node(f"con:{c.id}", kind="contractor", label=c.name)
            g.add_node(f"pkg:{c.scope_package}", kind="scope_package", label=c.scope_package)
            g.add_edge(f"con:{c.id}", f"pkg:{c.scope_package}", rel="scope_package")
        for r in reps.values():
            g.add_node(f"rep:{r.id}", kind="reporter", label=r.name)
            for wf in r.work_fronts or []:
                g.add_edge(f"rep:{r.id}", f"wf:{wf}", rel="assigned")
            if r.contractor:
                g.add_edge(f"rep:{r.id}", f"con:{r.contractor}", rel="employed_by")
        for a in acts.values():
            n = f"act:{a.activity_id}"
            g.add_node(n, kind="activity", label=a.name)
            if a.work_front:
                g.add_edge(n, f"wf:{a.work_front}", rel="located_at")
            for so in a.scope_objects or []:
                g.add_node(f"obj:{so}", kind="object", label=so)
                g.add_edge(n, f"obj:{so}", rel="scope")
            if a.line_no:
                g.add_edge(n, f"line:{a.line_no}", rel="line")
            for p in a.predecessors or []:
                g.add_edge(n, f"act:{p}", rel="predecessor")
            if a.scope_package:
                g.add_edge(n, f"pkg:{a.scope_package}", rel="package")

        aliases = []
        for w in wfs.values():
            for t in set([w.name.lower()] + list(w.aliases or [])):
                aliases.append((norm(t), "work_front", w.id, False))
        for l in lines.values():
            aliases.append((l.line_no.lower(), "line", l.line_no, False))
            aliases.append((l.drawing_no.lower(), "line", l.line_no, False))
            aliases.append((norm(l.system) + " line", "line", l.line_no, False))
        for al in session.exec(select(Alias)):
            aliases.append((norm(al.term), al.target_type, al.target_node, al.source == "planner"))
            g.add_node(f"alias:{al.term}", kind="alias", label=al.term)
            prefix = {"work_front": "wf", "line": "line", "object": "obj", "activity": "act"}.get(al.target_type)
            if prefix and f"{prefix}:{al.target_node}" in g:
                g.add_edge(f"alias:{al.term}", f"{prefix}:{al.target_node}", rel="alias")
        scopes = {(norm(al.term), al.target_node): al.scope_zone for al in session.exec(select(Alias)) if al.scope_zone}
        aliases = [a for a in aliases if len(a[0]) >= 3]
        aliases.sort(key=lambda a: -len(a[0]))
        return cls(g, acts, wfs, lines, objs, reps, cons, aliases, _version, scopes)

    def gazetteer(self) -> list[str]:
        """Place names the extractor should recognise (plan names + seeded + learned work-front aliases)."""
        return [t for t, ttype, _, _ in self.aliases if ttype == "work_front"]

    def refresh_dynamic(self, session: Session):
        """Pull current actual dates into the snapshots (cheap: ~150 rows)."""
        for aid, s, f in session.exec(select(Activity.activity_id, Activity.actual_start, Activity.actual_finish)):
            a = self.activities.get(aid)
            if a is not None:
                a.actual_start, a.actual_finish = s, f

    # ─────────────────────────────── lookups ───────────────────────────────
    def find_aliases(self, text: str) -> list[AliasHit]:
        """Longest-first, non-overlapping alias hits in the raw text (spans are into `text`)."""
        low = text.lower()
        taken: list[tuple[int, int]] = []
        hits = []
        for term, ttype, target, learned in self.aliases:
            pat = r"(?<![a-z0-9])" + r"[\s\-]*".join(re.escape(p) for p in term.split(" ")) + r"(?![a-z0-9])"
            for m in re.finditer(pat, low):
                s, e = m.span()
                if any(not (e <= a or s >= b) for a, b in taken):
                    continue
                taken.append((s, e))
                hits.append(AliasHit(term, (s, e), ttype, target, learned))
        return hits

    def lines_for_partial(self, partial: str) -> list[str]:
        return [l for l in self.lines if l.split("-")[0] == partial]

    def activities_at(self, wf_id: str) -> list[str]:
        n = f"wf:{wf_id}"
        if n not in self.g:
            return []
        return [x[4:] for x in self.g.neighbors(n) if x.startswith("act:")]

    def activities_for_line(self, line_no: str) -> list[str]:
        n = f"line:{line_no}"
        if n not in self.g:
            return []
        out = {x[4:] for x in self.g.neighbors(n) if x.startswith("act:")}
        for o in self.g.neighbors(n):                     # via objects of that line
            if o.startswith("obj:"):
                out |= {x[4:] for x in self.g.neighbors(o) if x.startswith("act:")}
        return sorted(out)

    def activities_for_object(self, obj_id: str) -> list[str]:
        n = f"obj:{obj_id}"
        if n not in self.g:
            return []
        return [x[4:] for x in self.g.neighbors(n) if x.startswith("act:")]

    def line_of_object(self, obj_id: str) -> str | None:
        o = self.objects.get(obj_id)
        return o.parent if o and o.parent in self.lines else None

    def work_fronts_in_unit(self, unit: str) -> list[str]:
        return [w.id for w in self.work_fronts.values() if w.unit == unit]

    def path(self, src: str, activity_id: str) -> list[str]:
        try:
            p = nx.shortest_path(self.g, src, f"act:{activity_id}")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        return [self._label(n) for n in p]

    def _label(self, n: str) -> str:
        kind, _, ident = n.partition(":")
        if kind == "rep":
            return f"Reporter {self.reporters[ident].name}" if ident in self.reporters else n
        if kind == "alias":
            return f"alias '{ident}'"
        return ident

    def stats(self) -> dict:
        kinds = {}
        for _, d in self.g.nodes(data=True):
            kinds[d.get("kind")] = kinds.get(d.get("kind"), 0) + 1
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges(), "by_kind": kinds,
                "aliases_learned": sum(1 for a in self.aliases if a[3])}
