// Unplanned work: classified, parent WBS suggested, change-order candidates flagged. We never author activity ids.
import { Download, Link2, FilePlus2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Empty, Input } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useControl } from "./ControlApp";

const CLS: Record<string, string> = { scope_creep: "#7c3aed", missing_activity: "#2563eb", rework: "#dc2626", site_prep: "#a16207", emergency: "#be123c" };

export default function UnplannedPage() {
  const { tick, notify } = useControl();
  const [rows, setRows] = useState<any[]>([]);
  const [linking, setLinking] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[]>([]);
  const load = () => api("/api/unplanned").then(setRows);
  useEffect(() => { load(); }, [tick]);
  useEffect(() => { if (q.length >= 2) api(`/api/review/activities/search?q=${encodeURIComponent(q)}`).then(setRes); else setRes([]); }, [q]);
  const act = async (id: number, action: string, activity_id?: string) => {
    await api(`/api/unplanned/${id}`, { method: "POST", json: { action, activity_id } });
    notify(action === "link" ? `EV-${id} linked to ${activity_id}` : `EV-${id} proposed as a new activity (CSV)`);
    setLinking(null); setQ("");
    load();
  };
  return (
    <Card>
      <CardHeader title="Unplanned work" subtitle="No candidate ≥ 0.50 — classified, with a suggested parent WBS. Proposals export as CSV with the activity id left blank for the planner."
        right={<a href="/api/unplanned/proposals.csv"><Button variant="outline" size="sm"><Download className="h-4 w-4" />Proposals CSV</Button></a>} />
      {rows.length === 0 ? <Empty>No unplanned work.</Empty> : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs muted"><tr className="border-b hairline"><th className="px-4 py-2">Event</th><th>Verbatim</th><th>Class</th><th>Suggested parent WBS</th><th>Zone</th><th>Status</th><th /></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b hairline align-top">
                <td className="px-4 py-2 font-mono text-xs"><Link className="underline" to={`/control/events/${r.id}`}>EV-{r.id}</Link><div className="muted">{fmtDate(r.date)} · {r.channel}</div></td>
                <td className="max-w-md py-2">“{r.text}”</td>
                <td className="py-2"><Badge color={CLS[r.class] || "#64748b"}>{(r.class || "").replace("_", " ")}</Badge>{r.change_order && <div className="mt-1"><Badge color="#c2410c">change-order candidate</Badge></div>}</td>
                <td className="py-2 font-mono text-xs">{r.parent_wbs}</td>
                <td className="py-2 text-xs">{r.zone || "—"}</td>
                <td className="py-2 text-xs">{r.status}</td>
                <td className="py-2 pr-4">
                  {linking === r.id ? (
                    <div className="relative w-64">
                      <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search activity…" />
                      <div className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border hairline bg-[var(--panel)] shadow-xl">
                        {res.map((a) => <button key={a.activity_id} onClick={() => act(r.id, "link", a.activity_id)} className="block w-full px-2 py-1 text-left text-xs hover:bg-[var(--panel-2)]"><b className="font-mono">{a.activity_id}</b> {a.name}</button>)}
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => setLinking(r.id)}><Link2 className="h-3.5 w-3.5" />Link</Button>
                      <Button size="sm" variant="blue" onClick={() => act(r.id, "propose")} disabled={r.status === "proposed"}><FilePlus2 className="h-3.5 w-3.5" />Propose</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
