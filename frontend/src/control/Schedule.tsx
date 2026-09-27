// Schedule: planned vs actual with the source event behind every actual date, variance, and PMIS write-back export.
import { Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Input, Select } from "@/components/ui";
import { ProvChip } from "@/components/domain";
import { api, fmtDate } from "@/lib/api";
import { useControl } from "./ControlApp";

const ST: Record<string, string> = { done: "#16a34a", in_progress: "#0ea5e9", late: "#dc2626", planned: "#94a3b8" };

export default function SchedulePage() {
  const { tick, discipline } = useControl();
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  useEffect(() => { api("/api/activities").then(setRows); }, [tick]);
  const list = useMemo(() => rows.filter((a) => (!discipline || a.discipline === discipline) && (!status || a.status === status)
    && (!q || (a.activity_id + a.name + (a.wf_name || "")).toLowerCase().includes(q.toLowerCase()))), [rows, q, status, discipline]);
  const v = (n: number | null) => n == null ? "—" : <span className={n > 0 ? "font-semibold text-red-600" : n < 0 ? "text-green-600" : ""}>{n > 0 ? "+" : ""}{n}d</span>;
  return (
    <Card>
      <CardHeader title={`Schedule (${list.length} of ${rows.length} L5/L6 activities)`} subtitle="Actual dates are written only by the pipeline (DERIVED) or a planner (HUMAN); each links to its source event."
        right={<div className="flex gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…" className="w-48" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option value="late">Late (not started)</option><option value="in_progress">In progress</option><option value="done">Done</option><option value="planned">Planned</option></Select>
          <a href="/api/schedule/export.csv"><Button variant="outline"><Download className="h-4 w-4" />PMIS write-back (XER CSV)</Button></a>
        </div>} />
      <div className="max-h-[75vh] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-[var(--panel)] text-left text-xs muted">
            <tr className="border-b hairline"><th className="px-4 py-2">Activity</th><th>WBS</th><th>Area</th><th>Planned</th><th>Actual start</th><th>Actual finish</th><th>Var S/F</th><th>Status</th><th>Events</th></tr>
          </thead>
          <tbody>
            {list.map((a) => (
              <tr key={a.activity_id} className="border-b hairline hover:bg-[var(--panel-2)]">
                <td className="px-4 py-1.5"><span className="font-mono font-semibold">{a.activity_id}</span> <span className="muted">{a.name}</span></td>
                <td className="font-mono text-[11px]">{a.wbs}</td>
                <td className="text-xs">{a.wf_name || "shop"}</td>
                <td className="text-xs">{fmtDate(a.planned_start)} → {fmtDate(a.planned_finish)}</td>
                <td className="text-xs">{a.actual_start ? <span className="inline-flex items-center gap-1">{fmtDate(a.actual_start)} <ProvChip tag={a.actual_start_prov} />
                  {a.actual_start_source_event && <Link className="font-mono text-teal-700 underline" to={`/control/events/${a.actual_start_source_event}`}>EV-{a.actual_start_source_event}</Link>}</span> : "—"}</td>
                <td className="text-xs">{a.actual_finish ? <span className="inline-flex items-center gap-1">{fmtDate(a.actual_finish)} <ProvChip tag={a.actual_finish_prov} />
                  {a.actual_finish_source_event && <Link className="font-mono text-teal-700 underline" to={`/control/events/${a.actual_finish_source_event}`}>EV-{a.actual_finish_source_event}</Link>}</span> : "—"}</td>
                <td className="text-xs">{v(a.var_start)} / {v(a.actual_finish ? a.var_finish : null)}</td>
                <td><Badge color={ST[a.status]}>{a.status.replace("_", " ")}</Badge></td>
                <td className="text-xs">{a.event_count ? <Link className="underline" to={`/control/events?activity=${a.activity_id}`}>{a.event_count}</Link> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
