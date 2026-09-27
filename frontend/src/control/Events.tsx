// Event Explorer (search + filters on every major field) and Event Detail (all 10 layers, provenance, state history, hash chain).
import { ChevronDown, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Empty, Input, Select } from "@/components/ui";
import { ConfPanel, MarginGauge, ProvChip, SpanHighlight, StateBadge } from "@/components/domain";
import { api, fmtDate, fmtTime, photoUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useControl } from "./ControlApp";

export function EventsPage() {
  const { tick, discipline } = useControl();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState(sp.get("q") || "");
  const f = Object.fromEntries(sp.entries());
  useEffect(() => {
    const p = new URLSearchParams(sp);
    if (discipline) p.set("discipline", discipline);
    api(`/api/events?${p.toString()}`).then(setRows);
  }, [tick, sp.toString(), discipline]);
  const set = (k: string, v: string) => { const p = new URLSearchParams(sp); v ? p.set(k, v) : p.delete(k); if (k !== "ids") p.delete("ids"); p.delete("label"); setSp(p); };
  return (
    <Card>
      <CardHeader title={`Event explorer · ${rows.length} events`} subtitle={f.label ? `Filtered from chart: ${f.label}` : f.ids ? `${f.ids.split(",").length} events from a chart click` : "Every input ends in a visible state — nothing is silently dropped."} />
      <div className="flex flex-wrap gap-2 px-4 pb-3">
        <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && set("q", q)} placeholder="Search text / activity / EV id ↵" className="w-64" />
        <Select value={f.state || ""} onChange={(e) => set("state", e.target.value)}>
          <option value="">Any state</option>{["linked", "review", "clarifying", "unplanned", "hse_hold", "duplicate", "unparseable"].map((s) => <option key={s}>{s}</option>)}
        </Select>
        <Select value={f.channel || ""} onChange={(e) => set("channel", e.target.value)}><option value="">Any channel</option>{["whatsapp", "pwa", "telegram", "dpr_upload", "spreadsheet"].map((s) => <option key={s}>{s}</option>)}</Select>
        <Select value={f.cause || ""} onChange={(e) => set("cause", e.target.value)}><option value="">Any cause</option>{["weather", "material", "permit_hse", "manpower", "equipment", "drawing_rev", "rework", "client_hold", "access", "power"].map((s) => <option key={s}>{s}</option>)}</Select>
        <Select value={f.match_path || ""} onChange={(e) => set("match_path", e.target.value)}><option value="">Any match path</option>{["kg_narrowed", "vector_only", "fuzzy_fallback"].map((s) => <option key={s}>{s}</option>)}</Select>
        <Input type="date" value={f.date_from || ""} onChange={(e) => set("date_from", e.target.value)} className="w-40" />
        <Input type="date" value={f.date_to || ""} onChange={(e) => set("date_to", e.target.value)} className="w-40" />
        {sp.toString() && <Button variant="ghost" onClick={() => { setSp(new URLSearchParams()); setQ(""); }}>Clear</Button>}
      </div>
      <div className="max-h-[72vh] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-[var(--panel)] text-left text-xs muted">
            <tr className="border-b hairline"><th className="px-4 py-2">EV</th><th>Date</th><th>State</th><th>Verbatim</th><th>Activity</th><th>E / M / D / V</th><th>Margin</th><th>Path</th><th>Channel</th></tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} onClick={() => nav(`/control/events/${e.id}`)} className="cursor-pointer border-b hairline hover:bg-[var(--panel-2)]">
                <td className="px-4 py-1.5 font-mono text-xs">EV-{e.id}</td>
                <td className="text-xs">{fmtDate(e.date)}</td>
                <td><StateBadge state={e.state} /></td>
                <td className="max-w-md truncate py-1.5">{e.blocker && <Badge color="#dc2626" className="mr-1">{e.cause || "blocker"}</Badge>}{e.text}</td>
                <td className="font-mono text-xs">{e.activity || "—"}{e.date_written && <span className="ml-1 text-green-600">● {e.date_written.replace("actual_", "")}</span>}</td>
                <td className="font-mono text-[11px]">{[e.extraction_conf, e.match_conf, e.date_conf, e.verification_conf].map((v: number) => (v == null ? "—" : v.toFixed(2))).join(" / ")}</td>
                <td className="font-mono text-[11px]">{e.margin?.toFixed(2) ?? "—"}</td>
                <td className="text-[11px]">{e.match_path}</td>
                <td className="text-[11px]">{e.channel}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <Empty>No events match.</Empty>}
      </div>
    </Card>
  );
}

const LAYERS: [string, string[]][] = [
  ["1 · Envelope", ["source_type", "source_doc_id", "channel", "reporting_date", "reporter_id", "contractor", "discipline", "device_id", "app_version", "input_language", "captured_at", "queued_at", "synced_at", "sync_lag_s", "offline_flag"]],
  ["2 · Core event", ["action", "object_event_type", "activity_inference", "object_class", "object_id", "object_ids", "object_qualifier", "line_ref", "drawing_no", "location_text", "quantity", "uom", "event_date", "source_sentence"]],
  ["3 · Location", ["gps_lat", "gps_lon", "gps_accuracy", "geofence_result", "geofence_zone_id", "location_zone_text", "location_conflict", "exif_gps", "exif_timestamp", "photo_recycled_flag"]],
  ["4 · Evidence", ["photo_ids", "photo_count", "cv_objects_detected", "cv_plausibility", "cv_model_version", "evidence_completeness", "verification_score"]],
  ["5 · Context", ["document_section", "location_zone_text", "affected_activities"]],
  ["6 · Blocker", ["blocker_flag", "cause_category", "cause_subcategory", "cause_text", "time_lost_h", "blocker_resolved_at", "affected_activities"]],
  ["7 · HSE", ["hse_event_flag", "stop_work_flag", "mishap_flag", "permit_status"]],
  ["8 · Resources", ["manpower_total", "manpower_by_trade", "manhours", "shift", "equipment_deployed", "equipment_idle_flag", "equipment_breakdown", "material_consumed", "material_shortage_flag", "material_item_id", "material_issued_status"]],
  ["9 · Weather", ["weather_reported", "weather_fetched", "weather_source", "weather_window", "weather_corroborates", "weather_severity"]],
  ["10 · Derived", ["matched_activity_id", "state", "route_reason", "proposed_write", "date_written", "dedup_key", "duplicate_of", "candidate_set_size", "match_path", "match_margin", "signals_fired", "match_rationale", "contradictions", "clarification_asked", "clarification_response", "clarification_latency_s", "clarification_count", "unplanned_flag", "unplanned_class", "suggested_parent_wbs", "change_order_candidate"]],
];
const REPORT_FIELDS = new Set(["source_type", "source_doc_id", "reporting_date", "contractor", "device_id", "app_version", "captured_at", "queued_at", "synced_at", "sync_lag_s", "offline_flag", "gps_lat", "gps_lon", "gps_accuracy"]);

const empty = (v: any) => v == null || v === "" || v === false || (Array.isArray(v) && !v.length) || (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);
const show = (v: any) => (typeof v === "object" ? JSON.stringify(v) : String(v));

export function EventDetail() {
  const { id } = useParams();
  const { meta } = useControl();
  const [d, setD] = useState<any>(null);
  const [verify, setVerify] = useState<any>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  useEffect(() => { setD(null); api(`/api/events/${id}`).then(setD); }, [id]);
  const layers = useMemo(() => {
    if (!d) return [];
    const src = (f: string) => (REPORT_FIELDS.has(f) ? d.report?.[f] : d.event[f] ?? d.report?.[f]);
    return LAYERS.map(([name, fs]) => [name, fs.map((f) => [f, src(f)] as [string, any]).filter(([, v]) => !empty(v))] as [string, [string, any][]]);
  }, [d]);
  if (!d) return <div className="muted">Loading…</div>;
  const e = d.event, r = d.report;
  const prov = { ...(r.provenance || {}), ...(e.provenance || {}) };
  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-lg font-bold">EV-{e.id}</span><StateBadge state={e.state} />
          <span className="text-sm muted">{d.reporter?.name} · {e.channel} · report #{r.id} ({d.siblings.length} event{d.siblings.length > 1 ? "s" : ""}: {d.siblings.map((s: number) => <Link key={s} className={cn("mx-0.5 font-mono underline", s === e.id && "font-bold")} to={`/control/events/${s}`}>{s}</Link>)})</span>
          {e.matched_activity_id && <Badge color="#0f766e">{e.matched_activity_id}</Badge>}
        </div>
        <div className="mt-3 rounded-xl bg-[var(--panel-2)] p-3 text-[17px]"><SpanHighlight full={r.raw_text} sentenceSpan={e.source_span} spans={e.spans} /></div>
        <div className="mt-2 text-xs muted">Raw payload (verbatim, GIVEN): “{r.raw_text.length > 300 ? r.raw_text.slice(0, 300) + "…" : r.raw_text}”{r.transcript_raw && r.transcript_raw !== r.raw_text ? ` · transcript_raw: “${r.transcript_raw}”` : ""}</div>
        <div className="mt-1 text-xs"><b>Route:</b> {e.route_reason}</div>
        {(e.photo_ids || []).length > 0 && <div className="mt-2 flex gap-2">{e.photo_ids.map((p: string) => <img key={p} src={photoUrl(p)} className="h-24 rounded-lg" alt="" />)}</div>}
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="space-y-4 p-4"><ConfPanel e={e} gate={meta.settings.gate} finish={e.activity_inference === "completes"} /><MarginGauge margin={e.match_margin} threshold={meta.settings.gate.margin} /></Card>
        <Card className="p-4">
          <div className="text-sm font-semibold">Top candidates</div>
          {(e.top_k_candidates || []).map((c: any) => (
            <div key={c.activity_id} className="mt-2 rounded-lg border hairline p-2 text-sm">
              <div className="flex justify-between"><span><b className="font-mono">{c.activity_id}</b> {c.name}</span><span className="font-mono">{c.score.toFixed(2)}</span></div>
              <div className="mt-1 flex flex-wrap gap-1">{c.signals.map((s: string) => <Badge key={s} color="#16a34a">{s}</Badge>)}{c.penalties.map((s: string) => <Badge key={s} color="#dc2626">−{s}</Badge>)}</div>
              {c.kg_path?.length > 0 && <div className="mt-1 text-[11px] muted">KG: {c.kg_path.join(" → ")}</div>}
            </div>
          ))}
        </Card>
      </div>
      <Card>
        <CardHeader title="All 10 layers" subtitle="Provenance chip on every value · empty optional sections are collapsed (sparse is normal)" />
        <div className="grid gap-2 px-4 pb-4 md:grid-cols-2">
          {layers.map(([name, fs]) => {
            const isOpen = open[name] ?? fs.length > 0;
            return (
              <div key={name} className="rounded-xl border hairline">
                <button onClick={() => setOpen({ ...open, [name]: !isOpen })} className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-semibold">
                  <span>{name} <span className="font-normal muted">({fs.length})</span></span><ChevronDown className={cn("h-4 w-4 transition", isOpen && "rotate-180")} />
                </button>
                {isOpen && fs.length > 0 && (
                  <div className="space-y-0.5 border-t hairline px-3 py-2">
                    {fs.map(([f, v]) => (
                      <div key={f} className="flex items-baseline gap-2 text-xs">
                        <span className="w-40 shrink-0 font-mono muted">{f}</span>
                        <span className="min-w-0 flex-1 break-words">{show(v)}</span>
                        <ProvChip tag={prov[f] || (f.startsWith("gps") || f.endsWith("_at") ? "GIVEN" : "DERIVED")} />
                      </div>
                    ))}
                  </div>
                )}
                {isOpen && fs.length === 0 && <div className="border-t hairline px-3 py-2 text-xs muted">Not present in this report — normal.</div>}
              </div>
            );
          })}
        </div>
      </Card>
      {d.hse.length > 0 && (
        <Card className="border-l-4 border-red-600 p-4">
          <div className="text-sm font-semibold text-red-600">HSE record</div>
          {d.hse.map((h: any) => <div key={h.id} className="mt-1 text-sm">#{h.id} {h.kind} · {h.hse_event_type} · {h.hse_severity} · status {h.status} · permit {h.permit_type} {h.permit_status}</div>)}
        </Card>
      )}
      <Card>
        <CardHeader title="State history & hash chain" subtitle="Append-only audit log for this event/report; each row's hash covers the previous row's hash."
          right={<Button variant="outline" onClick={() => api("/api/audit/verify", { method: "POST" }).then(setVerify)}><ShieldCheck className="h-4 w-4" />Verify integrity</Button>} />
        {verify && (
          <div className={cn("mx-4 mb-3 rounded-lg px-3 py-2 text-sm", verify.ok ? "bg-green-600/10 text-green-700" : "bg-red-600/10 text-red-700")}>
            {verify.ok ? `✅ Chain intact — ${verify.checked} entries recomputed, head ${verify.head.slice(0, 16)}…` : `❌ Broken at entry ${verify.broken_at}: ${verify.reason}`}
          </div>
        )}
        <div className="px-4 pb-4">
          {d.audit.map((a: any) => (
            <div key={a.id} className="flex gap-3 border-b hairline py-1.5 text-xs">
              <span className="w-28 shrink-0 muted">{fmtTime(a.at)}</span>
              <span className="w-40 shrink-0 font-semibold">{a.action}</span>
              <span className="w-24 shrink-0">{a.actor}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] muted" title={a.payload_json}>{a.payload_json}</span>
              <span className="shrink-0 font-mono text-[10px] muted" title={`prev ${a.prev_hash}`}>#{a.hash.slice(0, 10)}</span>
            </div>
          ))}
          {d.reviews.map((rv: any) => <div key={rv.id} className="mt-2 text-xs">Planner {rv.reviewer}: <b>{rv.planner_action}</b> {rv.corrected_activity_id && `→ ${rv.corrected_activity_id}`} {rv.correction_reason && `(${rv.correction_reason})`} in {rv.planner_review_seconds?.toFixed?.(0)} s {rv.alias_learned && <Badge color="#16a34a">learned {rv.alias_learned}</Badge>}</div>)}
        </div>
      </Card>
    </div>
  );
}
