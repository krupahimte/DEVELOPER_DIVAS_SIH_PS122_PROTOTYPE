// Global audit trail with hash-chain verification.
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Card, CardHeader } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useControl } from "./ControlApp";

export default function AuditPage() {
  const { tick } = useControl();
  const [rows, setRows] = useState<any[]>([]);
  const [v, setV] = useState<any>(null);
  const [aliases, setAliases] = useState<any[]>([]);
  useEffect(() => { api("/api/audit?limit=300").then(setRows); api("/api/aliases").then(setAliases); }, [tick]);
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader title="Audit trail (append-only, SHA-256 hash chain)" subtitle="hashₙ = sha256(prev_hash | actor | action | entity | payload | time). Editing any row breaks every hash after it."
          right={<Button onClick={() => api("/api/audit/verify", { method: "POST" }).then(setV)}><ShieldCheck className="h-4 w-4" />Verify audit chain</Button>} />
        {v && <div className={cn("mx-4 mb-3 rounded-lg px-3 py-2 text-sm font-medium", v.ok ? "bg-green-600/10 text-green-700" : "bg-red-600/10 text-red-700")}>
          {v.ok ? `✅ Intact — all ${v.checked} entries recomputed · head ${v.head.slice(0, 24)}…` : `❌ Broken at entry ${v.broken_at}: ${v.reason}`}</div>}
        <div className="max-h-[72vh] overflow-auto px-4 pb-4">
          {rows.map((a) => (
            <div key={a.id} className="flex gap-3 border-b hairline py-1 text-xs">
              <span className="w-10 shrink-0 font-mono muted">{a.id}</span><span className="w-28 shrink-0 muted">{fmtTime(a.at)}</span>
              <span className="w-36 shrink-0 font-semibold">{a.action}</span><span className="w-24 shrink-0">{a.actor}</span><span className="w-24 shrink-0 font-mono">{a.entity}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] muted" title={a.payload_json}>{a.payload_json}</span>
              <span className="shrink-0 font-mono text-[10px] muted">#{a.hash.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <CardHeader title={`Learned aliases (${aliases.length})`} subtitle="Planner decisions → KG alias edges" />
        <div className="px-4 pb-4">
          {aliases.map((a) => (
            <div key={a.id} className="border-b hairline py-1.5 text-sm">
              <b>“{a.term}”</b> → <span className="font-mono">{a.target_node}</span> <span className="text-xs muted">({a.target_type}{a.scope_zone ? `, only in ${a.scope_zone}` : ""})</span>
              <div className="text-[11px] muted">{fmtTime(a.at)} · from EV-{a.learned_from_event}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
