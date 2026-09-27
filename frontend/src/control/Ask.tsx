// Ask the Project — searchable memory. Structured questions → filters over the event table (in Python); narrative → retrieval with event citations.
import { Search, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Input } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";

const EXAMPLES = ["Why is Rack B piping late?", "How many rain delays in Unit 3 in September?", "Why was PIP-3-2340 late?", "How many equipment delays?", "What happened at the cooling tower basin?"];

export default function AskPage() {
  const [q, setQ] = useState("");
  const [a, setA] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const ask = async (text = q) => {
    if (!text.trim()) return;
    setQ(text);
    setBusy(true);
    try { setA(await api("/api/ask", { method: "POST", json: { q: text } })); } finally { setBusy(false); }
  };
  const linkify = (s: string) => s.split(/(\[EV-\d+\])/).map((p, i) => {
    const m = p.match(/\[EV-(\d+)\]/);
    return m ? <Link key={i} to={`/control/events/${m[1]}`} className="rounded bg-teal-700/10 px-1 font-mono text-xs text-teal-700 underline">EV-{m[1]}</Link> : <span key={i}>{p}</span>;
  });
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Card className="p-4">
        <div className="flex gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} placeholder="Ask the project… e.g. Why is Rack B piping late?" className="h-11 text-base" />
          <Button size="lg" onClick={() => ask()} disabled={busy}><Search className="h-4 w-4" />{busy ? "…" : "Ask"}</Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">{EXAMPLES.map((x) => <button key={x} onClick={() => ask(x)} className="rounded-full border hairline px-3 py-1 text-xs hover:bg-[var(--panel-2)]">{x}</button>)}</div>
      </Card>
      {a && (
        <Card>
          <CardHeader title={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-teal-700" />Answer</span>}
            subtitle={a.kind === "structured" ? "Structured question → filters over cause / unit / zone / date (rejected & duplicate events excluded)" : a.generator === "claude" ? "Claude, from retrieved snippets only (cited)" : "Extractive answer from retrieved field text (no LLM key) — every line cited"} />
          <div className="whitespace-pre-wrap px-4 pb-3 text-[15px] leading-7">{linkify(a.answer)}</div>
          {a.filters && <div className="mx-4 mb-3 rounded-lg bg-[var(--panel-2)] px-3 py-2 font-mono text-[11px] muted">{a.filters}</div>}
          {a.citations?.length > 0 && (
            <div className="border-t hairline px-4 py-3">
              <div className="mb-2 text-xs font-semibold muted">Sources ({a.citations.length})</div>
              <div className="space-y-1">
                {a.citations.map((c: any) => (
                  <Link key={c.event_id} to={`/control/events/${c.event_id}`} className="flex items-baseline gap-2 rounded px-1 text-sm hover:bg-[var(--panel-2)]">
                    <span className="font-mono text-xs text-teal-700">EV-{c.event_id}</span><span className="text-xs muted">{fmtDate(c.date)}</span>
                    {c.cause && <Badge color="#dc2626">{c.cause}</Badge>}<span className="truncate">“{c.text}”</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
