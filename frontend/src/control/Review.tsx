// Review Queue — the planner's main work screen. Must be fast: keyboard first, one decision per item.
// A approve · 1/2/3 pick candidate · R reject · U unplanned · J/K next/prev
import { AlertTriangle, ArrowRight, Check, GitBranch, Image as ImageIcon, Timer, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Card, Empty, Input, Kbd, Select } from "@/components/ui";
import { ConfPanel, FIELD_COLOR, MarginGauge, ProvChip, SpanHighlight, StateBadge } from "@/components/domain";
import { api, fmtDate, fmtTime, photoUrl } from "@/lib/api";
import { useSession } from "@/lib/role";
import { cn } from "@/lib/utils";
import { useControl } from "./ControlApp";

const REASONS = [["wrong_area", "Wrong area"], ["wrong_object", "Wrong object"], ["terminology", "Terminology (site word)"]];

export default function ReviewPage() {
  const { tick, notify, meta } = useControl();
  const sess = useSession();
  const [queue, setQueue] = useState<any[]>([]);
  const [sel, setSel] = useState(0);
  const [detail, setDetail] = useState<any>(null);
  const [pending, setPending] = useState<{ activity_id: string; name: string } | null>(null);
  const [reason, setReason] = useState("terminology");
  const [alias, setAlias] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const started = useRef(Date.now());
  const [secs, setSecs] = useState(0);
  const gate = meta.settings.gate;

  const load = useCallback(() => api("/api/review/queue").then(setQueue), []);
  useEffect(() => { load(); }, [tick]);
  const cur = queue[Math.min(sel, queue.length - 1)];
  useEffect(() => {
    setDetail(null); setPending(null); setAlias(""); setSearch(""); setResults([]);
    started.current = Date.now();
    if (cur) api(`/api/events/${cur.id}`).then(setDetail);
  }, [cur?.id]);
  useEffect(() => { const i = setInterval(() => setSecs(Math.round((Date.now() - started.current) / 1000)), 500); return () => clearInterval(i); }, []);
  useEffect(() => {
    if (!pending || !cur) return;
    api(`/api/review/${cur.id}/suggest-alias?activity_id=${pending.activity_id}&reason=${reason}`).then((r) => setAlias(r.term || ""));
  }, [pending?.activity_id, reason]);
  useEffect(() => { if (search.length >= 2) api(`/api/review/activities/search?q=${encodeURIComponent(search)}`).then(setResults); else setResults([]); }, [search]);

  const decide = async (action: string, activity_id?: string, why?: string) => {
    if (!cur) return;
    const seconds = (Date.now() - started.current) / 1000;
    const r = await api(`/api/review/${cur.id}`, { method: "POST", json: { action, activity_id, reason: why, reviewer: sess?.user || "R-IYER", seconds, alias_term: alias || undefined } });
    if (r.alias_learned) notify(`Learned: ${r.alias_learned}`, "green");
    else notify(`${action === "approve" ? "Approved" : action === "reject" ? "Rejected" : action === "unplanned" ? "Marked unplanned" : "Corrected"} EV-${cur.id} in ${seconds.toFixed(0)} s` + (r.date_written ? ` · wrote ${r.date_written.replace("_", " ")}` : ""));
    await load();
  };

  const pick = (i: number) => {
    const c = detail?.event?.top_k_candidates?.[i];
    if (!c) return;
    if (i === 0) decide("approve", c.activity_id);
    else setPending({ activity_id: c.activity_id, name: c.name });
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "SELECT") return;
      const k = e.key.toLowerCase();
      if (k === "j") setSel((s) => Math.min(queue.length - 1, s + 1));
      else if (k === "k") setSel((s) => Math.max(0, s - 1));
      else if (k === "a") pick(0);
      else if (["1", "2", "3"].includes(k)) pick(+k - 1);
      else if (k === "r") decide("reject");
      else if (k === "u") decide("unplanned");
      else if (k === "enter" && pending) decide("correct", pending.activity_id, reason);
      else if (k === "escape") setPending(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Card className="flex max-h-[calc(100vh-110px)] flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b hairline px-3 py-2">
          <div className="text-sm font-semibold">Review queue <span className="muted">({queue.length})</span></div>
          <div className="flex gap-1 text-[10px] muted"><Kbd>J</Kbd><Kbd>K</Kbd> move</div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {queue.length === 0 && <Empty>Queue is empty — everything is linked, asked, or held for HSE.</Empty>}
          {queue.map((q, i) => (
            <button key={q.id} onClick={() => setSel(i)} className={cn("block w-full border-b hairline px-3 py-2 text-left", i === sel ? "bg-teal-700/10 ring-2 ring-inset ring-teal-600" : "hover:bg-[var(--panel-2)]")}>
              <div className="flex items-center gap-2 text-[11px] muted"><span className="font-mono">EV-{q.id}</span>·<span>{fmtDate(q.date)}</span>·<span>{q.channel}</span><span className="ml-auto"><StateBadge state={q.state} /></span></div>
              <div className="mt-0.5 line-clamp-2 text-sm">{q.text}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {q.blocker && <Badge color="#dc2626">blocker</Badge>}
                {(q.contradictions || []).map((c: string) => <Badge key={c} color="#dc2626">{c.split(":")[0].replace(/_/g, " ")}</Badge>)}
                {q.top && <Badge color="#0f766e">{q.top.activity_id} · {q.top.score.toFixed(2)}</Badge>}
              </div>
            </button>
          ))}
        </div>
      </Card>

      <div className="min-w-0 space-y-3">
        {!cur ? <Card><Empty>Nothing selected.</Empty></Card> : !detail ? <Card><Empty>Loading…</Empty></Card> : (
          <Detail d={detail} q={cur} gate={gate} hover={hover} setHover={setHover} secs={secs}
            onPick={pick} onDecide={decide} pending={pending} setPending={setPending} reason={reason} setReason={setReason}
            alias={alias} setAlias={setAlias} search={search} setSearch={setSearch} results={results} />
        )}
      </div>
    </div>
  );
}

function Detail({ d, q, gate, hover, setHover, secs, onPick, onDecide, pending, setPending, reason, setReason, alias, setAlias, search, setSearch, results }: any) {
  const e = d.event, r = d.report;
  const finish = e.activity_inference === "completes";
  const fields: [string, any][] = useMemo(() => [
    ["action", e.action], ["object_event_type", e.object_event_type], ["activity_inference", e.activity_inference], ["object_class", e.object_class],
    ["object_qualifier", e.object_qualifier], ["object_ids", (e.object_ids || []).join(", ")], ["line_ref", e.line_ref], ["location_text", e.location_text],
    ["quantity", e.quantity != null ? `${e.quantity} ${e.uom || ""}` : null], ["event_date", e.event_date], ["manpower_by_trade", Object.entries(e.manpower_by_trade || {}).map(([k, v]) => `${v} ${k}`).join(", ")],
    ["cause_category", e.cause_category], ["time_lost_h", e.time_lost_h], ["weather_reported", e.weather_reported],
    ["geofence_result", e.geofence_result && `${e.geofence_result}${e.geofence_zone_id ? " · " + e.geofence_zone_id : ""}`],
    ["material_issued_status", e.material_issued_status && `${e.material_item_id}: ${e.material_issued_status}`],
    ["weather_fetched", e.weather_fetched?.rain_mm != null ? `${e.weather_fetched.rain_mm_window ?? e.weather_fetched.rain_mm} mm (${e.weather_source}) → corroborates: ${e.weather_corroborates}` : null],
    ["photo_ids", (e.photo_ids || []).length ? `${e.photo_ids.length} photo · CV ${e.cv_plausibility ?? "—"}` : null],
  ].filter(([, v]) => v != null && v !== "") as any, [e]);

  return (
    <>
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs muted">
          <span className="font-mono text-sm font-semibold text-[var(--ink)]">EV-{e.id}</span><StateBadge state={e.state} />
          <span>{d.reporter?.name || "unknown reporter"}</span>·<span>{e.channel}</span>·<span>captured {fmtTime(r.captured_at)}</span>
          {r.offline_flag && <Badge color="#d97706">offline {Math.round((r.sync_lag_s || 0) / 360) / 10} h</Badge>}
          <span className="ml-auto inline-flex items-center gap-1 font-mono"><Timer className="h-3.5 w-3.5" />{secs}s</span>
        </div>
        <div className="mt-3 rounded-xl bg-[var(--panel-2)] p-3 text-[17px]">
          <SpanHighlight full={r.raw_text} sentenceSpan={e.source_span} spans={e.spans} active={hover} onHover={setHover} />
        </div>
        {r.transcript_raw && r.transcript_raw !== r.raw_text && <div className="mt-1 text-xs muted">Original transcript (verbatim): {r.transcript_raw}</div>}
        <div className="mt-2 text-xs muted">Route: {e.route_reason}</div>
        <div className="mt-3 grid gap-4 md:grid-cols-[1fr_auto]">
          <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
            {fields.map(([f, v]) => (
              <div key={f} className={cn("flex items-baseline gap-2 rounded px-1 text-sm", hover === f && "bg-[var(--panel-2)]")} onMouseEnter={() => setHover(f)} onMouseLeave={() => setHover(null)}>
                <span className="w-32 shrink-0 font-mono text-[11px] muted" style={{ borderLeft: `3px solid ${FIELD_COLOR[f] || "transparent"}`, paddingLeft: 4 }}>{f}</span>
                <span className="min-w-0 flex-1 truncate">{String(v)}</span>
                <ProvChip tag={e.provenance?.[f] || e.provenance?.[f.split("_")[0]]} />
              </div>
            ))}
          </div>
          {(e.photo_ids || []).length > 0 && (
            <div className="w-40">
              <img src={photoUrl(e.photo_ids[0])} className="rounded-lg" alt="evidence" />
              <div className="mt-1 text-[10px] muted"><ImageIcon className="mr-0.5 inline h-3 w-3" />EXIF {e.exif_timestamp ? fmtTime(e.exif_timestamp) : "none"} {e.photo_recycled_flag && <b className="text-red-600">· OLD PHOTO</b>}</div>
              <div className="text-[10px] muted">CV: {(e.cv_objects_detected || []).join(", ")}</div>
            </div>
          )}
        </div>
      </Card>

      <div className="grid gap-3 xl:grid-cols-2">
        <Card className="space-y-4 p-4">
          <div className="text-sm font-semibold">Four confidences — never averaged</div>
          <ConfPanel e={e} gate={gate} finish={finish} />
          <MarginGauge margin={e.match_margin} threshold={gate.margin} />
        </Card>
        <Card className="space-y-2 p-4">
          <div className="text-sm font-semibold">Proposed write</div>
          <div className="rounded-lg bg-teal-700/10 px-3 py-2 font-mono text-sm">{e.proposed_write || "—"}</div>
          <div className="flex items-center gap-2 text-sm">
            <Badge color="#7c3aed">text says: {e.object_event_type || "—"}</Badge><ArrowRight className="h-4 w-4 muted" /><Badge color="#0f766e">activity level: {e.activity_inference || "—"}</Badge>
          </div>
          {e.field_conf?._inference_why && <div className="text-xs muted">Why this inference: {e.field_conf._inference_why}</div>}
          {(e.field_conf?._failing?.length > 0 || (e.match_margin != null && e.match_margin < gate.margin)) && (
            <div className="flex flex-wrap items-center gap-1 text-xs">
              <span className="muted">Held back by:</span>
              {(e.field_conf?._failing || []).map((f: string) => <Badge key={f} color="#dc2626">{f} below threshold</Badge>)}
              {e.match_margin != null && e.match_margin < gate.margin && <Badge color="#dc2626">match margin {e.match_margin.toFixed(2)} &lt; {gate.margin.toFixed(2)}</Badge>}
            </div>
          )}
          {(e.contradictions || []).length > 0 && (
            <div className="space-y-1 pt-1">
              {e.contradictions.map((c: string) => (
                <div key={c} className="flex items-center gap-2 rounded-lg bg-red-500/10 px-2 py-1 text-sm text-red-700 dark:text-red-300">
                  <AlertTriangle className="h-4 w-4" /> {({ material_not_issued: "Material not issued from store", predecessor_open: "Predecessor not finished", location_conflict: "Location conflict (text/GPS vs activity)", old_photo_exif: "Old photo (EXIF > 24 h before capture)", weather_not_corroborated: "Weather claim not corroborated" } as any)[c.split(":")[0]] || c} <span className="font-mono text-xs">{c.split(":")[1] || ""}</span>
                </div>
              ))}
            </div>
          )}
          <div className="pt-1 text-xs muted">{e.match_rationale}</div>
        </Card>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {(e.top_k_candidates || []).map((c: any, i: number) => (
          <Card key={c.activity_id} className={cn("p-3", i === 0 && "ring-2 ring-teal-600/50")}>
            <div className="flex items-center justify-between"><Kbd>{i + 1}</Kbd><span className="font-mono text-lg font-bold">{c.score.toFixed(2)}</span></div>
            <div className="mt-1 font-mono text-sm font-semibold">{c.activity_id}</div>
            <div className="text-sm">{c.name}</div>
            <div className="mt-1 text-[11px] muted">{c.wf_name || "—"} · planned {fmtDate(c.planned_start)} → {fmtDate(c.planned_finish)}{c.actual_start ? ` · started ${fmtDate(c.actual_start)}` : ""}</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {c.signals.map((s: string) => <Badge key={s} color="#16a34a">{s}</Badge>)}
              {c.penalties.map((s: string) => <Badge key={s} color="#dc2626">−{s}</Badge>)}
            </div>
            {c.kg_path?.length > 0 && <div className="mt-2 flex items-center gap-1 text-[11px] muted"><GitBranch className="h-3 w-3" />{c.kg_path.join(" → ")}</div>}
            <Button size="sm" variant={i === 0 ? "success" : "outline"} className="mt-3 w-full" onClick={() => onPick(i)}>
              {i === 0 ? <><Check className="h-4 w-4" />Approve</> : "Choose this"}
            </Button>
          </Card>
        ))}
      </div>

      {pending && (
        <Card className="space-y-3 border-2 border-teal-600 p-4">
          <div className="text-sm">Correct to <b className="font-mono">{pending.activity_id}</b> — {pending.name}. Why was the suggestion wrong?</div>
          <div className="flex flex-wrap gap-2">
            {REASONS.map(([k, l]) => <Button key={k} size="sm" variant={reason === k ? "default" : "outline"} onClick={() => setReason(k)}>{l}</Button>)}
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="muted">Teach the site word:</span>
            <Input value={alias} onChange={(ev) => setAlias(ev.target.value)} placeholder="(nothing will be learned)" className="max-w-xs" />
            <span className="text-xs muted">→ becomes a KG alias edge</span>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => onDecide("correct", pending.activity_id, reason)}><Check className="h-4 w-4" /> Save correction <Kbd>Enter</Kbd></Button>
            <Button variant="ghost" onClick={() => setPending(null)}>Cancel <Kbd>Esc</Kbd></Button>
          </div>
        </Card>
      )}

      <Card className="flex flex-wrap items-center gap-2 p-3">
        <Button variant="success" onClick={() => onPick(0)} disabled={!e.top_k_candidates?.length}><Check className="h-4 w-4" />Approve top <Kbd>A</Kbd></Button>
        <Button variant="blue" onClick={() => onDecide("unplanned")}>Mark unplanned <Kbd>U</Kbd></Button>
        <Button variant="outline" onClick={() => onDecide("reject")}><X className="h-4 w-4" />Reject <Kbd>R</Kbd></Button>
        <div className="relative ml-auto w-full max-w-sm">
          <Input value={search} onChange={(ev) => setSearch(ev.target.value)} placeholder="Reassign to any activity… (id, name, area)" />
          {results.length > 0 && (
            <div className="absolute bottom-10 z-20 max-h-64 w-full overflow-y-auto rounded-lg border hairline bg-[var(--panel)] shadow-xl">
              {results.map((a: any) => (
                <button key={a.activity_id} onClick={() => { setPending({ activity_id: a.activity_id, name: a.name }); setSearch(""); }}
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--panel-2)]">
                  <span className="font-mono">{a.activity_id}</span> {a.name} <span className="text-xs muted">{a.wf_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </Card>
    </>
  );
}
