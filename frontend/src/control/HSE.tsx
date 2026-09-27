// HSE Centre — every item here reached a human regardless of match confidence. Text is verbatim.
import { ShieldAlert, UserCheck, CheckCircle2, OctagonX, FileWarning } from "lucide-react";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Empty, Input, Select } from "@/components/ui";
import { api, fmtTime, photoUrl } from "@/lib/api";
import { useSession } from "@/lib/role";
import { cn } from "@/lib/utils";
import { useControl } from "./ControlApp";

const SEV_COLOR: Record<string, string> = { critical: "#7f1d1d", major: "#dc2626", minor: "#f97316", observation: "#eab308" };

export default function HSEPage() {
  const { tick, meta, notify } = useControl();
  const sess = useSession();
  const [items, setItems] = useState<any[]>([]);
  const [permits, setPermits] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [note, setNote] = useState("");
  const [show, setShow] = useState("open");
  const load = () => {
    api("/api/hse").then((r) => { setItems(r); setSel((s: any) => (s ? r.find((x: any) => x.id === s.id) : r[0])); });
    api("/api/hse/permits").then(setPermits);
  };
  useEffect(load, [tick]);
  const act = async (action: string, extra: any = {}) => {
    await api(`/api/hse/${sel.id}`, { method: "POST", json: { action, actor: sess?.user || "R-HAZARIKA", ...extra } });
    notify(`HSE item #${sel.id}: ${action}`, "red");
    setNote("");
    load();
  };
  const list = items.filter((h) => (show === "all" ? true : show === "open" ? h.status !== "closed" : h.status === "closed"));
  const zone = sel?.work_front && meta.work_fronts.find((w: any) => w.id === sel.work_front);
  const radius = sel?.stop_work_scope === "site" ? meta.work_fronts : sel?.stop_work_scope === "unit" && zone ? meta.work_fronts.filter((w: any) => w.unit === zone.unit) : zone ? [zone] : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 rounded-2xl border-l-8 border-red-600 bg-red-50 px-4 py-3 dark:bg-red-950/40">
        <ShieldAlert className="h-7 w-7 text-red-600" />
        <div>
          <div className="text-lg font-bold text-red-700 dark:text-red-300">HSE Centre</div>
          <div className="text-sm text-red-900/80 dark:text-red-200/80">Safety events are never auto-synced. A near-miss matched at 0.98 still lands here. Text is shown verbatim — never summarised.</div>
        </div>
        <Select className="ml-auto" value={show} onChange={(e) => setShow(e.target.value)}><option value="open">Open</option><option value="closed">Closed</option><option value="all">All</option></Select>
      </div>
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card className="max-h-[70vh] overflow-y-auto">
          {list.length === 0 && <Empty>No items.</Empty>}
          {list.map((h) => (
            <button key={h.id} onClick={() => setSel(h)} className={cn("block w-full border-b hairline px-3 py-2 text-left", sel?.id === h.id ? "bg-red-500/10 ring-2 ring-inset ring-red-500" : "hover:bg-[var(--panel-2)]")}>
              <div className="flex items-center gap-2 text-[11px]">
                <Badge color={SEV_COLOR[h.hse_severity]}>{h.hse_severity}</Badge>
                <Badge color="#dc2626">{h.kind === "permit" ? `${(h.permit_type || "").replace("_", " ")} permit ${h.permit_status}` : (h.hse_event_type || "").replace("_", " ")}</Badge>
                <span className="ml-auto muted">{h.status}</span>
              </div>
              <div className="mt-1 text-sm">“{h.hse_event_text}”</div>
              <div className="mt-0.5 text-[11px] muted">#{h.id} · {h.work_front} · {fmtTime(h.created_at)}</div>
            </button>
          ))}
        </Card>
        {sel ? (
          <div className="space-y-4">
            <Card className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color={SEV_COLOR[sel.hse_severity]}>{sel.hse_severity}</Badge>
                <span className="text-sm font-semibold">HSE #{sel.id} · {sel.kind}</span>
                <span className="text-xs muted">status: <b>{sel.status}</b>{sel.assigned_to ? ` · assigned ${sel.assigned_to}` : ""}</span>
                <Link to={`/control/events/${sel.event_id}`} className="ml-auto text-xs text-teal-700 underline">EV-{sel.event_id} →</Link>
              </div>
              <blockquote className="mt-3 rounded-xl border-l-4 border-red-600 bg-red-500/5 px-4 py-3 text-lg">“{sel.hse_event_text}”</blockquote>
              <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                {sel.kind === "permit" && <>
                  <Row k="Permit type" v={sel.permit_type} /><Row k="Permit status" v={<b className="text-red-600">{sel.permit_status}</b>} />
                  <Row k="Permit id" v={sel.permit_id || "— none on record"} /><Row k="Validity window" v={sel.permit_validity_window || "—"} />
                  <Row k="Gas test" v={sel.gas_test_done == null ? "—" : sel.gas_test_done ? "done" : "not done"} />
                </>}
                {sel.kind !== "permit" && <>
                  <Row k="Event type" v={sel.hse_event_type} /><Row k="Mishap" v={sel.mishap_flag ? `yes · ${sel.mishap_category || ""}` : "no"} />
                  <Row k="Equipment" v={sel.equipment_id || "—"} /><Row k="Rework triggered" v={sel.rework_triggered ? "yes" : "no"} />
                </>}
                <Row k="Zone" v={sel.work_front} /><Row k="Reported to" v={sel.hse_reported_to} />
                <Row k="Would have matched" v={sel.info_match_activity ? `${sel.info_match_activity} @ ${sel.info_match_conf?.toFixed(2)} — HELD, not synced` : "—"} />
              </div>
              {(sel.photo_ids || []).length > 0 && <img src={photoUrl(sel.photo_ids[0])} className="mt-3 max-h-40 rounded-lg" alt="" />}
              <div className="mt-4 rounded-xl bg-[var(--panel-2)] p-3">
                <div className="flex items-center gap-2 text-sm font-semibold"><OctagonX className="h-4 w-4 text-red-600" /> Stop-work scope {sel.stop_work_scope ? `: ${sel.stop_work_scope}` : "— set the blast radius"}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {["activity", "zone", "unit", "site"].map((s) => <Button key={s} size="sm" variant={sel.stop_work_scope === s ? "danger" : "outline"} onClick={() => act("scope", { stop_work_scope: s })}>{s}</Button>)}
                </div>
                <div className="mt-2 text-xs muted">Gated activities ({(sel.gated_activities || []).length}): {(sel.gated_activities || []).join(", ") || "—"}</div>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={() => act("acknowledge")}><UserCheck className="h-4 w-4" />Acknowledge</Button>
                <Select onChange={(e) => e.target.value && act("assign", { assigned_to: e.target.value })} defaultValue="">
                  <option value="">Assign to…</option>
                  {meta.reporters.filter((r: any) => ["hse", "supervisor", "pm"].includes(r.role)).map((r: any) => <option key={r.id} value={r.name}>{r.name}</option>)}
                </Select>
                <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Closing note (required)" className="max-w-xs" />
                <Button variant="danger" disabled={!note.trim()} onClick={() => act("close", { note })}><CheckCircle2 className="h-4 w-4" />Close</Button>
              </div>
            </Card>
            <Card>
              <CardHeader title="Blast radius" subtitle="Zone / unit / site covered by this item" />
              <div className="h-64 px-3 pb-3">
                <MapContainer bounds={[[27.4646, 95.3362], [27.4760, 95.3442]]} scrollWheelZoom={false} style={{ height: "100%" }} key={sel.id + (sel.stop_work_scope || "")}>
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
                  <GeoJSON data={{ type: "FeatureCollection", features: meta.work_fronts.map((w: any) => ({ type: "Feature", properties: { id: w.id, name: w.name, hit: radius.some((r: any) => r.id === w.id) }, geometry: { type: "Polygon", coordinates: [w.polygon] } })) } as any}
                    style={(f: any) => ({ color: f.properties.hit ? "#dc2626" : "#94a3b8", weight: f.properties.hit ? 3 : 1, fillOpacity: f.properties.hit ? 0.35 : 0.05, fillColor: "#dc2626" })}
                    onEachFeature={(f: any, l: any) => l.bindTooltip(f.properties.name)} />
                </MapContainer>
              </div>
            </Card>
          </div>
        ) : <Card><Empty>Select an item.</Empty></Card>}
      </div>
      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><FileWarning className="h-4 w-4 text-red-600" />Permit board</span>} subtitle="By zone: valid · expiring soon (<24 h) · expired · pending · missing (an open activity needs it)" />
        <div className="grid gap-3 px-4 pb-4 md:grid-cols-2 xl:grid-cols-5">
          {meta.work_fronts.map((w: any) => {
            const ps = permits.filter((p) => p.work_front === w.id);
            return (
              <div key={w.id} className="rounded-xl border hairline p-2">
                <div className="text-xs font-semibold">{w.name} <span className="muted">· {w.unit}</span></div>
                <div className="mt-1 space-y-1">
                  {ps.length === 0 && <div className="text-[11px] muted">no permits needed</div>}
                  {ps.map((p, i) => (
                    <div key={i} className="flex items-center justify-between gap-1 text-[11px]">
                      <span>{p.type.replace("_", " ")}</span>
                      <Badge color={{ valid: "#16a34a", expiring_soon: "#d97706", expired: "#dc2626", pending: "#6b7280", missing: "#7f1d1d", revoked: "#7f1d1d" }[p.status as string]}>
                        {p.status.replace("_", " ")}{p.permit_id ? "" : p.needed_by ? ` · ${p.needed_by}` : ""}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return <div className="flex gap-2"><span className="w-36 shrink-0 muted">{k}</span><span>{v ?? "—"}</span></div>;
}
