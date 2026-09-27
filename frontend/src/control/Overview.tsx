// The "wow" page: KPIs + 14 charts, all computed from the event store, all click-through.
import { Activity as ActivityIcon, AlertTriangle, CheckCircle2, Clock, Inbox, Layers, ShieldAlert, Timer, Waypoints } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, CircleMarker, Popup, TileLayer, Tooltip as LTooltip } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart, ReferenceLine,
  ResponsiveContainer, Sankey, Tooltip, XAxis, YAxis, Layer, Rectangle,
} from "recharts";
import { Card, CardHeader, Select } from "@/components/ui";
import { api, CAT, CHANNEL_COLOR, DISC_COLOR, fmtDate, PATH_COLOR, STATE_COLOR } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useControl } from "./ControlApp";

const d5 = (s: string) => fmtDate(s);

export default function Overview() {
  const { tick, discipline, meta } = useControl();
  const [area, setArea] = useState("WF-U3-RACK-B");
  const [d, setD] = useState<any>(null);
  const nav = useNavigate();
  useEffect(() => {
    api(`/api/analytics/overview?area=${area}${discipline ? `&discipline=${discipline}` : ""}`).then(setD);
  }, [tick, area, discipline]);
  const go = (ids: number[] | undefined, label?: string) => ids?.length && nav(`/control/events?ids=${ids.join(",")}${label ? `&label=${encodeURIComponent(label)}` : ""}`);
  if (!d) return <div className="muted">Loading dashboard…</div>;
  const k = d.kpis;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Kpi icon={<Inbox />} label="Reports today" value={k.reports_today} sub={`${k.events_total} events total`} onClick={() => nav("/control/events")} />
        <Kpi icon={<Layers />} label="Events today" value={k.events_today} sub={`${k.activities_started} started · ${k.activities_finished} finished`} />
        <Kpi icon={<CheckCircle2 />} label="Auto-sync %" value={`${k.auto_sync_pct}%`} sub={`today ${k.auto_sync_pct_today}%`} tone="green" />
        <Kpi icon={<ActivityIcon />} label="In review" value={k.in_review} tone="amber" onClick={() => nav("/control/review")} />
        <Kpi icon={<Waypoints />} label="Unplanned" value={k.unplanned_open} tone="blue" onClick={() => nav("/control/unplanned")} />
        <Kpi icon={<ShieldAlert />} label="Open HSE items" value={k.hse_open} tone="red" onClick={() => nav("/control/hse")} />
        <Kpi icon={<Timer />} label="Avg planner review" value={`${k.avg_review_s}s`} sub="per decision" />
        <Kpi icon={<Clock />} label="Avg sync lag" value={`${k.avg_sync_lag_h}h`} sub="captured → server" />
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader title="1 · Routing funnel" subtitle="Reports → events → where the gate sent them (hover a band; click a route for its events)" />
          <FunnelSankey data={d.funnel} />
          <div className="flex flex-wrap gap-2 px-4 pb-3 text-xs">
            {Object.entries(d.funnel.routes).map(([r, n]: any) => (
              <span key={r} className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: STATE_COLOR[r] }} />{r} <b>{n}</b></span>
            ))}
          </div>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader title="13 · Site map" subtitle="Geofences coloured by status · pins = last 7 days of reports · hollow red = outside geofence" />
          <SiteMap data={d.map} onPin={(id: number) => nav(`/control/events/${id}`)} />
        </Card>
      </div>

      <Card>
        <CardHeader title="2 · Planned vs actual" subtitle="Grey = planned · colour = actual (◆ where the date came from, variance in days) · click a bar for its source events"
          right={<Select value={area} onChange={(e) => setArea(e.target.value)}>{meta.work_fronts.map((w: any) => <option key={w.id} value={w.id}>{w.name} ({w.unit})</option>)}
            <option value="Unit 3">All Unit 3</option><option value="Unit 2">All Unit 2</option></Select>} />
        <Gantt rows={d.gantt.rows} today={d.today} onPick={(r: any) => go([...(r.events || []), ...(r.blockers || [])], r.id)} />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardHeader title="3 · Schedule variance by discipline" subtitle="Average slip in days (positive = late)" />
          <div className="h-60 px-2 pb-2">
            <ResponsiveContainer><BarChart data={d.variance} barGap={2}>
              <CartesianGrid vertical={false} /><XAxis dataKey="discipline" tickFormatter={(v) => v.slice(0, 5)} /><YAxis />
              <Tooltip /><Legend /><ReferenceLine y={0} stroke="#94a3b8" />
              <Bar dataKey="start_slip" name="Start slip (d)" fill={CAT[0]} radius={[4, 4, 0, 0]} />
              <Bar dataKey="finish_slip" name="Finish slip (d)" fill={CAT[1]} radius={[4, 4, 0, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Pareto data={d.pareto} onPick={(ids: number[], c: string) => go(ids, `cause: ${c}`)} />
        <WeatherChart data={d.weather} onPick={(ids: number[]) => go(ids, "weather claims")} />
        <Card>
          <CardHeader title="6 · Discipline productivity" subtitle="Quantity per manhour (events with qty + manpower) · day vs night shift" />
          <div className="h-44 px-2">
            <ResponsiveContainer><LineChart data={d.productivity.rows}>
              <CartesianGrid vertical={false} /><XAxis dataKey="day" tickFormatter={d5} /><YAxis /><Tooltip labelFormatter={d5} /><Legend />
              {d.productivity.disciplines.map((x: string) => <Line key={x} dataKey={x} stroke={DISC_COLOR[x]} strokeWidth={2} dot={{ r: 3 }} connectNulls />)}
            </LineChart></ResponsiveContainer>
          </div>
          <div className="h-28 px-2 pb-2">
            <ResponsiveContainer><BarChart data={d.productivity.shift} layout="vertical" barGap={2}>
              <XAxis type="number" hide /><YAxis type="category" dataKey="discipline" width={90} /><Tooltip /><Legend />
              <Bar dataKey="day" name="Day shift" fill={CAT[3]} radius={[0, 4, 4, 0]} /><Bar dataKey="night" name="Night shift" fill={CAT[6]} radius={[0, 4, 4, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardHeader title="7 · Manpower by trade per day" subtitle="Stacked, from extracted manpower_by_trade" />
          <div className="h-44 px-2">
            <ResponsiveContainer><AreaChart data={d.manpower.rows}>
              <CartesianGrid vertical={false} /><XAxis dataKey="day" tickFormatter={d5} /><YAxis /><Tooltip labelFormatter={d5} /><Legend />
              {d.manpower.trades.slice(0, 8).map((t: string, i: number) => <Area key={t} type="monotone" dataKey={t} stackId="1" stroke={CAT[i]} fill={CAT[i]} fillOpacity={0.55} />)}
            </AreaChart></ResponsiveContainer>
          </div>
          <div className="px-4 text-xs font-semibold">Equipment utilisation (event mentions)</div>
          <div className="h-32 px-2 pb-2">
            <ResponsiveContainer><BarChart data={d.equipment} layout="vertical">
              <XAxis type="number" hide /><YAxis type="category" dataKey="equipment" width={100} /><Tooltip /><Legend />
              <Bar dataKey="working" stackId="e" fill={STATE_COLOR.linked} /><Bar dataKey="idle" stackId="e" fill={STATE_COLOR.review} />
              <Bar dataKey="breakdown" stackId="e" fill={STATE_COLOR.hse_hold} radius={[0, 4, 4, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <ConfidenceHealth data={d.confidence} />
        <Card>
          <CardHeader title="9 · Match path mix" subtitle="Which matcher tier produced the top candidate" />
          <div className="grid grid-cols-5 gap-2 px-2 pb-2">
            <div className="col-span-2 h-48">
              <ResponsiveContainer><PieChart>
                <Pie data={d.match_path.total} dataKey="value" nameKey="name" innerRadius={42} outerRadius={70} paddingAngle={2}
                  onClick={(p: any) => nav(`/control/events?match_path=${p.name}`)}>
                  {d.match_path.total.map((x: any) => <Cell key={x.name} fill={PATH_COLOR[x.name]} stroke="var(--panel)" strokeWidth={2} />)}
                </Pie><Tooltip />
              </PieChart></ResponsiveContainer>
            </div>
            <div className="col-span-3 h-48">
              <ResponsiveContainer><BarChart data={d.match_path.by_day}>
                <XAxis dataKey="day" tickFormatter={d5} /><YAxis /><Tooltip labelFormatter={d5} /><Legend />
                {["kg_narrowed", "vector_only", "fuzzy_fallback"].map((k) => <Bar key={k} dataKey={k} stackId="p" fill={PATH_COLOR[k]} />)}
              </BarChart></ResponsiveContainer>
            </div>
          </div>
        </Card>
        <LearningCurve data={d.learning} />
        <Card>
          <CardHeader title="12 · Channel adoption" subtitle="Reports per day by channel" />
          <div className="h-60 px-2 pb-2">
            <ResponsiveContainer><BarChart data={d.channels.rows}>
              <CartesianGrid vertical={false} /><XAxis dataKey="day" tickFormatter={d5} /><YAxis /><Tooltip labelFormatter={d5} /><Legend />
              {d.channels.names.map((c: string, i: number) => <Bar key={c} dataKey={c} stackId="c" fill={CHANNEL_COLOR[c] || CAT[i]} />)}
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <SyncHeat data={d.sync_lag} />
        <FillRate data={d.fill_rate} />
      </div>
    </div>
  );
}

function Kpi({ icon, label, value, sub, tone, onClick }: any) {
  const c = { green: "text-green-600", amber: "text-amber-600", blue: "text-blue-600", red: "text-red-600" }[tone as string] || "text-teal-700";
  return (
    <button onClick={onClick} className={cn("panel p-3 text-left", onClick && "hover:ring-2 hover:ring-teal-600/30", tone === "red" && value > 0 && "ring-2 ring-red-500/60")}>
      <div className={cn("flex items-center gap-1.5 text-xs font-medium muted [&_svg]:h-3.5 [&_svg]:w-3.5")}>{icon}{label}</div>
      <div className={cn("mt-1 text-2xl font-bold tabular-nums", c)}>{value}</div>
      {sub && <div className="text-[11px] muted">{sub}</div>}
    </button>
  );
}

function FunnelSankey({ data }: any) {
  const nav = useNavigate();
  const Node = (p: any) => {
    const name = data.nodes[p.index]?.name;
    const color = STATE_COLOR[name] || (name === "Reports" || name === "Events" ? "#0f766e" : name.startsWith("Linked") || name.startsWith("Approved") ? STATE_COLOR.linked : "#94a3b8");
    return (
      <Layer key={`n${p.index}`}>
        <Rectangle x={p.x} y={p.y} width={p.width} height={p.height} fill={color} radius={2} style={{ cursor: "pointer" }}
          onClick={() => { const st = ({ "HSE hold": "hse_hold", Unplanned: "unplanned", Review: "review,clarifying", Duplicate: "duplicate", Pending: "review,clarifying" } as Record<string, string>)[name]; st && nav(`/control/events?state=${st}`); }} />
        <text x={p.x + p.width + 6} y={p.y + p.height / 2} dominantBaseline="middle" fontSize={11} fill="var(--ink)">{name} ({name === "Reports" ? data.reports : p.payload.value})</text>
      </Layer>
    );
  };
  return (
    <div className="h-72 px-2">
      <ResponsiveContainer>
        <Sankey data={data} node={<Node />} nodePadding={18} margin={{ left: 10, right: 150, top: 10, bottom: 10 }} link={{ stroke: "#0f766e", strokeOpacity: 0.18 }}>
          <Tooltip />
        </Sankey>
      </ResponsiveContainer>
    </div>
  );
}

function Gantt({ rows, today, onPick }: any) {
  const t0 = useMemo(() => Math.min(...rows.map((r: any) => +new Date(r.ps)), +new Date(today) - 20 * 864e5), [rows]);
  const t1 = useMemo(() => Math.max(...rows.map((r: any) => +new Date(r.pf)), +new Date(today) + 10 * 864e5), [rows]);
  const x = (s: string) => ((+new Date(s) - t0) / (t1 - t0)) * 100;
  const todayX = x(today);
  const ticks: string[] = [];
  for (let t = t0; t <= t1; t += 7 * 864e5) ticks.push(new Date(t).toISOString().slice(0, 10));
  if (!rows.length) return <div className="p-6 text-sm muted">No activities in this area.</div>;
  return (
    <div className="overflow-x-auto px-4 pb-4">
      <div className="min-w-[760px]">
        <div className="relative ml-[260px] h-5 text-[10px] muted">
          {ticks.map((t) => <span key={t} className="absolute -translate-x-1/2" style={{ left: `${x(t)}%` }}>{fmtDate(t)}</span>)}
        </div>
        {rows.map((r: any) => {
          const late = r.var_start != null && r.var_start > 0;
          const col = r.af ? STATE_COLOR.linked : r.as ? (late ? STATE_COLOR.review : "#0ea5e9") : late ? STATE_COLOR.hse_hold : "#94a3b8";
          const aEnd = r.af || (r.as ? today : null);
          return (
            <div key={r.id} className="group flex h-8 cursor-pointer items-center hover:bg-[var(--panel-2)]" onClick={() => onPick(r)}>
              <div className="w-[260px] shrink-0 truncate pr-2 text-xs"><span className="font-mono font-semibold">{r.id}</span> <span className="muted">{r.name}</span></div>
              <div className="relative h-full flex-1">
                <div className="absolute top-1/2 h-px w-full bg-[var(--line)]" />
                <div className="absolute inset-y-0 border-l-2 border-dashed border-red-400/70" style={{ left: `${todayX}%` }} />
                <div className="absolute top-[7px] h-[7px] rounded-sm bg-slate-300 dark:bg-slate-600" style={{ left: `${x(r.ps)}%`, width: `${Math.max(0.6, x(r.pf) - x(r.ps))}%` }} title={`Planned ${r.ps} → ${r.pf}`} />
                {r.as && aEnd && (
                  <div className="absolute top-[16px] h-[8px] rounded-sm" style={{ left: `${x(r.as)}%`, width: `${Math.max(0.6, x(aEnd) - x(r.as))}%`, background: col }}
                    title={`Actual ${r.as} → ${r.af || "in progress"}`} />
                )}
                {r.as && <Diamond left={x(r.as)} color={col} title={`Actual Start ${r.as} from EV-${r.as_event ?? "PMIS baseline"} (${r.as_prov || ""})`} />}
                {r.af && <Diamond left={x(r.af)} color={col} title={`Actual Finish ${r.af} from EV-${r.af_event ?? "PMIS"} (${r.af_prov || ""})`} />}
                {r.blockers?.length > 0 && <AlertTriangle className="absolute top-1 h-3.5 w-3.5 text-red-500" style={{ left: `calc(${x(r.ps)}% - 16px)` }} />}
                <span className="absolute top-[6px] text-[10px] font-semibold" style={{ left: `calc(${Math.max(x(r.pf), aEnd ? x(aEnd) : 0)}% + 6px)`, color: r.var_start > 0 ? "#dc2626" : "var(--muted)" }}>
                  {r.var_start != null ? `${r.var_start > 0 ? "+" : ""}${r.var_start}d` : ""}{r.var_finish != null ? ` / ${r.var_finish > 0 ? "+" : ""}${r.var_finish}d` : ""}
                </span>
              </div>
            </div>
          );
        })}
        <div className="mt-2 flex flex-wrap gap-4 text-[11px] muted">
          <span>▬ planned</span><span style={{ color: STATE_COLOR.linked }}>▬ finished</span><span style={{ color: "#0ea5e9" }}>▬ in progress</span>
          <span style={{ color: STATE_COLOR.review }}>▬ started late</span><span style={{ color: STATE_COLOR.hse_hold }}>◆ not started, late</span><span>◆ actual date source (hover)</span>
          <span className="text-red-500">⚠ blockers reported</span><span className="text-red-500">┆ project date</span>
        </div>
      </div>
    </div>
  );
}

function Diamond({ left, color, title }: any) {
  return <div title={title} className="absolute top-[14px] h-3 w-3 -translate-x-1/2 rotate-45 border-2 border-white" style={{ left: `${left}%`, background: color }} />;
}

function Pareto({ data, onPick }: any) {
  const [mode, setMode] = useState("count");
  const rows = data.find((p: any) => p.mode === mode)?.rows || [];
  const tot = rows.reduce((a: number, r: any) => a + r.value, 0) || 1;
  const pr = rows.map((r: any) => ({ ...r, share: +(100 * r.value / tot).toFixed(1) }));
  return (
    <Card>
      <CardHeader title="4 · Delay causes (Pareto)" subtitle="Share of total and cumulative %, one 0–100% axis · click a bar"
        right={<Select value={mode} onChange={(e) => setMode(e.target.value)}><option value="count">by count</option><option value="hours">by hours lost</option></Select>} />
      <div className="h-60 px-2 pb-2">
        <ResponsiveContainer><ComposedChart data={pr}>
          <CartesianGrid vertical={false} /><XAxis dataKey="cause" tickFormatter={(v) => v.replace("_", " ").slice(0, 9)} /><YAxis unit="%" domain={[0, 100]} />
          <Tooltip formatter={(v: any, n: any, p: any) => (n === "Share" ? [`${v}% (${p.payload.value} ${mode === "count" ? "events" : "h"})`, n] : [`${v}%`, n])} /><Legend />
          <Bar dataKey="share" name="Share" fill={CAT[0]} radius={[4, 4, 0, 0]} onClick={(p: any) => onPick(p.events, p.cause)} cursor="pointer" />
          <Line dataKey="cum_pct" name="Cumulative" stroke={CAT[1]} strokeWidth={2} dot={{ r: 4 }} />
          <ReferenceLine y={80} stroke="#94a3b8" strokeDasharray="4 3" label={{ value: "80%", position: "right", fontSize: 10 }} />
        </ComposedChart></ResponsiveContainer>
      </div>
    </Card>
  );
}

function WeatherChart({ data, onPick }: any) {
  return (
    <Card>
      <CardHeader title="5 · Weather claims vs evidence" subtitle="Claims per day by corroboration (top) · fetched rain mm at site (bottom) · click a day" />
      <div className="h-36 px-2">
        <ResponsiveContainer><BarChart data={data} syncId="wx">
          <XAxis dataKey="day" hide /><YAxis allowDecimals={false} width={30} /><Tooltip labelFormatter={d5} /><Legend />
          <Bar dataKey="corroborated" stackId="w" fill={STATE_COLOR.linked} onClick={(p: any) => onPick(p.events)} cursor="pointer" />
          <Bar dataKey="not_corroborated" name="not corroborated" stackId="w" fill={STATE_COLOR.hse_hold} onClick={(p: any) => onPick(p.events)} cursor="pointer" />
          <Bar dataKey="unavailable" stackId="w" fill={STATE_COLOR.duplicate} radius={[4, 4, 0, 0]} />
        </BarChart></ResponsiveContainer>
      </div>
      <div className="h-24 px-2 pb-2">
        <ResponsiveContainer><AreaChart data={data} syncId="wx">
          <XAxis dataKey="day" tickFormatter={d5} /><YAxis width={30} unit="" /><Tooltip labelFormatter={d5} formatter={(v: any) => [`${v} mm`, "rain fetched"]} />
          <Area dataKey="rain_mm" stroke={CAT[0]} fill={CAT[0]} fillOpacity={0.25} strokeWidth={2} />
        </AreaChart></ResponsiveContainer>
      </div>
    </Card>
  );
}

function ConfidenceHealth({ data }: any) {
  const g = data.thresholds;
  const H = ({ k, label, thr }: any) => (
    <div>
      <div className="text-[11px] font-medium">{label}</div>
      <div className="h-20">
        <ResponsiveContainer><BarChart data={data[k]} barCategoryGap={1}>
          <XAxis dataKey="bin" hide /><Tooltip formatter={(v: any) => [v, "events"]} labelFormatter={(l) => `${l}–${(+l + 0.1).toFixed(1)}`} />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>{data[k].map((b: any) => <Cell key={b.bin} fill={+b.bin + 0.1 <= thr ? "#cbd5e1" : CAT[0]} />)}</Bar>
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
  return (
    <Card>
      <CardHeader title="8 · Confidence health" subtitle="Four separate scores (never blended) · grey bins fall below the gate" />
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 px-4">
        <H k="extraction" label="extraction" thr={g.extraction} /><H k="match" label="match" thr={g.match} />
        <H k="date" label="date" thr={g.date} /><H k="verification" label="verification" thr={g.verification} />
      </div>
      <div className="px-4 pt-1 text-[11px] font-medium">match margin (top-1 − top-2), gate at {g.margin}</div>
      <div className="h-24 px-2 pb-2">
        <ResponsiveContainer><BarChart data={data.margin} barCategoryGap={1}>
          <XAxis dataKey="bin" tickFormatter={(v) => (+v * 100) % 20 === 0 ? v : ""} /><Tooltip />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>{data.margin.map((b: any) => <Cell key={b.bin} fill={+b.bin < g.margin ? STATE_COLOR.review : CAT[0]} />)}</Bar>
          <ReferenceLine x={g.margin.toFixed(2)} stroke="#dc2626" strokeDasharray="3 3" />
        </BarChart></ResponsiveContainer>
      </div>
    </Card>
  );
}

function LearningCurve({ data }: any) {
  return (
    <Card>
      <CardHeader title="10 · Learning curve — gets smarter every week" subtitle="Aliases learned from planner decisions (top) · auto-sync % and clarify rate, 7-day rolling (bottom)" />
      <div className="h-24 px-2">
        <ResponsiveContainer><AreaChart data={data} syncId="lc">
          <XAxis dataKey="day" hide /><YAxis allowDecimals={false} width={30} /><Tooltip labelFormatter={d5} />
          <Area type="stepAfter" dataKey="aliases" name="aliases learned" stroke={CAT[6]} fill={CAT[6]} fillOpacity={0.2} strokeWidth={2} />
        </AreaChart></ResponsiveContainer>
      </div>
      <div className="h-36 px-2 pb-2">
        <ResponsiveContainer><LineChart data={data} syncId="lc">
          <CartesianGrid vertical={false} /><XAxis dataKey="day" tickFormatter={d5} /><YAxis unit="%" width={40} domain={[0, 100]} /><Tooltip labelFormatter={d5} /><Legend />
          <Line dataKey="auto_pct" name="auto-sync %" stroke={STATE_COLOR.linked} strokeWidth={2} dot={false} />
          <Line dataKey="clarify_rate" name="clarify rate %" stroke={STATE_COLOR.clarifying} strokeWidth={2} dot={false} />
        </LineChart></ResponsiveContainer>
      </div>
    </Card>
  );
}

function SyncHeat({ data }: any) {
  const wfs = [...new Set(data.map((r: any) => r.name))].sort() as string[];
  const days = [...new Set(data.map((r: any) => r.day))].sort() as string[];
  const get = (w: string, d: string) => data.find((r: any) => r.name === w && r.day === d)?.lag_h;
  const col = (h?: number) => (h == null ? "transparent" : h < 0.25 ? "#e0f2f1" : h < 2 ? "#99d5cf" : h < 6 ? "#2a9d8f" : h < 12 ? "#1d6f66" : "#0b3d38");
  return (
    <Card>
      <CardHeader title="11 · Sync lag heatmap" subtitle="Avg hours from capture to server, by work front × day (connectivity quality)" />
      <div className="overflow-x-auto px-4 pb-4">
        <table className="text-[10px]">
          <thead><tr><th />{days.map((d) => <th key={d} className="px-0.5 font-normal muted">{d.slice(8)}</th>)}</tr></thead>
          <tbody>{wfs.map((w) => (
            <tr key={w}><td className="whitespace-nowrap pr-2 text-xs">{w}</td>
              {days.map((d) => { const h = get(w, d); return <td key={d} className="p-[1px]"><div title={h == null ? "no reports" : `${w} ${d}: ${h} h`} className="h-5 w-5 rounded-sm" style={{ background: col(h), outline: h == null ? "1px dashed var(--line)" : undefined }} /></td>; })}
            </tr>))}</tbody>
        </table>
        <div className="mt-2 flex items-center gap-1 text-[10px] muted">lag: {["<15 min", "<2 h", "<6 h", "<12 h", "≥12 h"].map((l, i) => <span key={l} className="inline-flex items-center gap-1"><span className="h-3 w-3 rounded-sm" style={{ background: col([0.1, 1, 3, 8, 20][i]) }} />{l}</span>)}</div>
      </div>
    </Card>
  );
}

function FillRate({ data }: any) {
  return (
    <Card>
      <CardHeader title="14 · Field fill rate" subtitle={`% of events where each field is present — answers the schema's open questions. Events with an explicit object id / line: ${data.object_id_share}%`} />
      <div className="grid grid-cols-1 gap-x-6 px-4 pb-4 md:grid-cols-2">
        {data.rows.map((r: any) => (
          <div key={r.field} className="flex items-center gap-2 py-0.5 text-xs">
            <span className="w-40 truncate font-mono">{r.field}</span>
            <div className="h-2 flex-1 rounded-full bg-[var(--panel-2)]"><div className="h-2 rounded-full" style={{ width: `${r.pct}%`, background: r.pct < 10 ? "#94a3b8" : CAT[0] }} /></div>
            <span className="w-12 text-right tabular-nums">{r.pct}%</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

const STATUS_FILL: Record<string, string> = { hse: "#dc2626", late: "#d97706", active: "#16a34a", idle: "#94a3b8" };

function SiteMap({ data, onPin }: any) {
  return (
    <div className="h-[330px] px-3 pb-3">
      <MapContainer bounds={[[27.4646, 95.3362], [27.4760, 95.3442]]} scrollWheelZoom={false} style={{ height: "100%" }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
        <GeoJSON data={data.geo} style={(f: any) => ({ color: STATUS_FILL[f.properties.status], weight: 2, fillOpacity: 0.25, fillColor: STATUS_FILL[f.properties.status] })}
          onEachFeature={(f: any, l: any) => l.bindTooltip(`<b>${f.properties.name}</b> (${f.properties.unit})<br/>in progress ${f.properties.in_progress} · late ${f.properties.late} · done ${f.properties.done}${f.properties.hse_open ? `<br/><b style="color:#dc2626">HSE open: ${f.properties.hse_open}</b>` : ""}`)} />
        {data.pins.map((p: any) => (
          <CircleMarker key={p.event_id} center={[p.lat, p.lon]} radius={p.outside ? 7 : 5}
            pathOptions={{ color: p.outside ? "#dc2626" : STATE_COLOR[p.state], fillColor: STATE_COLOR[p.state], fillOpacity: p.outside ? 0 : 0.9, weight: 2 }}
            eventHandlers={{ click: () => onPin(p.event_id) }}>
            <LTooltip>EV-{p.event_id} · {p.state} · {p.day}<br />{p.text}</LTooltip>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="mt-1 flex gap-3 text-[10px] muted">
        {Object.entries(STATUS_FILL).map(([k, c]) => <span key={k} className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{k === "hse" ? "HSE open" : k}</span>)}
      </div>
    </div>
  );
}
