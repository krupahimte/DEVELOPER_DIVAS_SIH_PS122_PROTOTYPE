// DPR generation + document ingest (messy xlsx, DPR PDF/text, WhatsApp chat export).
import { FileSpreadsheet, FileText, MessageSquareText, Printer, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, Input, Select } from "@/components/ui";
import { StateBadge } from "@/components/domain";
import { upload } from "@/lib/api";
import { useControl } from "./ControlApp";

export default function DocsPage() {
  const { meta, notify } = useControl();
  const [day, setDay] = useState("2026-09-13");
  const [disc, setDisc] = useState("");
  const [area, setArea] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const q = `day=${day}${disc ? `&discipline=${disc}` : ""}${area ? `&area=${encodeURIComponent(area)}` : ""}`;
  const send = async (kind: string, f?: File | null, name?: string) => {
    let file = f;
    if (!file && name) file = new File([await (await fetch(`/api/samples/${name}`)).blob()], name);
    if (!file) return;
    setBusy(kind);
    try {
      const r = await upload(`/api/upload/${kind}`, file);
      setRes({ kind, ...r });
      const n = r.events?.length ?? r.reports?.reduce((a: number, x: any) => a + x.events.length, 0);
      notify(`${file.name}: ${n} events created`, "green");
    } catch (e: any) { notify(String(e.message || e), "red"); } finally { setBusy(""); }
  };
  const evs = res ? res.events || res.reports?.flatMap((r: any) => r.events) || [] : [];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><Printer className="h-4 w-4" />End-of-day DPR reconstruction</span>}
          subtitle="Built only from the day's events — progress, manpower, equipment, blockers with verbatim cause text, HSE, weather reported vs fetched. Every line cites its source event." />
        <div className="flex flex-wrap items-end gap-2 px-4 pb-4">
          <label className="text-xs muted">Date<Input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="mt-1 w-44" /></label>
          <label className="text-xs muted">Discipline<Select value={disc} onChange={(e) => setDisc(e.target.value)} className="mt-1 block"><option value="">All</option>{meta.disciplines.map((d: string) => <option key={d}>{d}</option>)}</Select></label>
          <label className="text-xs muted">Area<Select value={area} onChange={(e) => setArea(e.target.value)} className="mt-1 block"><option value="">All</option><option>Unit 2</option><option>Unit 3</option>{meta.work_fronts.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}</Select></label>
          <a href={`/api/dpr?${q}`} target="_blank"><Button><FileText className="h-4 w-4" />Generate DPR (HTML)</Button></a>
          <a href={`/api/dpr?${q}&format=pdf`} target="_blank"><Button variant="outline">PDF</Button></a>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        <UploadCard icon={<FileSpreadsheet />} title="Spreadsheet DPR (.xlsx)" desc="Fuzzy header mapping ('Desc of Work' → description, 'Qty Done' → quantity, 'Nos' → uom). One row = one candidate event. No LLM."
          sample="dpr_25sep_messy_headers.xlsx" busy={busy === "xlsx"} onFile={(f) => send("xlsx", f)} onSample={(n) => send("xlsx", null, n)} accept=".xlsx" />
        <UploadCard icon={<FileText />} title="DPR PDF / text" desc="pdfplumber → section split by area headings → sentence split → extraction. Headings give location context."
          sample="dpr_piping_24sep.pdf" busy={busy === "dpr"} onFile={(f) => send("dpr", f)} onSample={(n) => send("dpr", null, n)} accept=".pdf,.txt" />
        <UploadCard icon={<MessageSquareText />} title="WhatsApp chat export" desc="'[dd/mm/yy, h:mm] Name: message' → one report per message, reporter matched by name, Hinglish handled."
          sample="whatsapp_chat_export_hinglish.txt" busy={busy === "chat"} onFile={(f) => send("chat", f)} onSample={(n) => send("chat", null, n)} accept=".txt" />
      </div>
      {res && (
        <Card>
          <CardHeader title={`Result — ${evs.length} events`} subtitle={res.mapping ? `Header row ${res.header_row} · reporting date ${res.reporting_date}` : undefined} />
          {res.mapping && (
            <div className="flex flex-wrap gap-2 px-4 pb-3">
              {res.mapping.map((m: any) => <Badge key={m.header} color="#0f766e">“{m.header}” → {m.field} ({m.score})</Badge>)}
            </div>
          )}
          <div className="px-4 pb-4">
            {evs.map((e: any) => (
              <Link key={e.id} to={`/control/events/${e.id}`} className="flex items-center gap-3 border-b hairline py-1.5 text-sm hover:bg-[var(--panel-2)]">
                <span className="w-16 font-mono text-xs">EV-{e.id}</span><StateBadge state={e.state} /><span className="flex-1 truncate">{e.text}</span><span className="font-mono text-xs">{e.activity || ""}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function UploadCard({ icon, title, desc, sample, busy, onFile, onSample, accept }: { icon: any; title: string; desc: string; sample: string; busy: boolean; onFile: (f: File) => void; onSample: (n: string) => void; accept: string }) {
  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-center gap-2 text-sm font-semibold [&_svg]:h-4 [&_svg]:w-4">{icon}{title}</div>
      <p className="mt-1 flex-1 text-xs muted">{desc}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <label className="cursor-pointer"><span className="inline-flex h-9 items-center gap-2 rounded-lg bg-teal-700 px-4 text-sm font-medium text-white"><Upload className="h-4 w-4" />{busy ? "Processing…" : "Upload"}</span>
          <input type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} /></label>
        <Button variant="outline" onClick={() => onSample(sample)} disabled={busy}>Use sample</Button>
      </div>
      <a href={`/api/samples/${sample}`} className="mt-2 text-[11px] muted underline">{sample}</a>
    </Card>
  );
}
