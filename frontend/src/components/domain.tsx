// Domain widgets shared across Control Room pages.
import { PROV_COLOR, STATE_COLOR } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "./ui";

export function ProvChip({ tag }: { tag?: string }) {
  if (!tag) return null;
  const c = PROV_COLOR[tag] || "#64748b";
  return (
    <span title={`provenance: ${tag}`} className="rounded px-1 py-[1px] font-mono text-[9px] font-semibold tracking-wide" style={{ color: c, background: c + "18", border: `1px solid ${c}35` }}>
      {tag}
    </span>
  );
}

const STATE_LABEL: Record<string, string> = {
  linked: "linked", review: "review", clarifying: "clarifying", unplanned: "unplanned", hse_hold: "HSE hold", duplicate: "duplicate", unparseable: "unparseable",
};
export function StateBadge({ state }: { state: string }) {
  return <Badge color={STATE_COLOR[state] || "#64748b"}>{STATE_LABEL[state] || state}</Badge>;
}

export function ConfBar({ label, value, threshold }: { label: string; value?: number | null; threshold: number }) {
  const v = value ?? 0;
  const ok = v >= threshold;
  const near = !ok && threshold - v <= 0.15;
  const color = ok ? "#16a34a" : near ? "#d97706" : "#dc2626";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="font-mono" style={{ color }}>
          {value == null ? "—" : v.toFixed(2)} <span className="muted">/ {threshold.toFixed(2)}</span>
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-[var(--panel-2)]">
        <div className="h-2 rounded-full transition-all" style={{ width: `${Math.min(100, v * 100)}%`, background: color }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-slate-500" style={{ left: `${threshold * 100}%` }} title="threshold" />
      </div>
    </div>
  );
}

export function ConfPanel({ e, gate, finish }: { e: any; gate: any; finish?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-3">
      <ConfBar label="Extraction — read it right?" value={e.extraction_conf} threshold={gate.extraction} />
      <ConfBar label="Match — right activity?" value={e.match_conf} threshold={gate.match} />
      <ConfBar label="Date — right day?" value={e.date_conf} threshold={gate.date} />
      <ConfBar label={`Verification — evidence?${finish ? " (finish bar)" : ""}`} value={e.verification_conf} threshold={finish ? gate.verification_finish : gate.verification} />
    </div>
  );
}

export function MarginGauge({ margin, threshold }: { margin?: number | null; threshold: number }) {
  const m = margin ?? 0;
  const ok = m >= threshold;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium">Match margin (top-1 − top-2)</span>
        <span className="font-mono" style={{ color: ok ? "#16a34a" : "#dc2626" }}>{margin == null ? "—" : m.toFixed(2)} <span className="muted">≥ {threshold.toFixed(2)}</span></span>
      </div>
      <div className="relative h-2 rounded-full bg-[var(--panel-2)]">
        <div className="h-2 rounded-full" style={{ width: `${Math.min(100, (m / 0.5) * 100)}%`, background: ok ? "#16a34a" : "#dc2626" }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-slate-500" style={{ left: `${(threshold / 0.5) * 100}%` }} />
      </div>
      {!ok && margin != null && <div className="mt-1 text-[11px] text-red-600">Two candidates fit almost equally — a coin flip wearing a high-confidence costume.</div>}
    </div>
  );
}

// Colour per extracted field for span highlighting
export const FIELD_COLOR: Record<string, string> = {
  action: "#7c3aed", object_event_type: "#db2777", object_qualifier: "#0ea5e9", object_class: "#0284c7", object_ids: "#0369a1",
  line_ref: "#0891b2", drawing_no: "#0891b2", location_text: "#16a34a", quantity: "#ca8a04", uom: "#ca8a04", event_date: "#ea580c",
  manpower_by_trade: "#9333ea", manpower_total: "#9333ea", cause_category: "#dc2626", cause_text: "#fca5a5", time_lost_h: "#b91c1c",
  weather_reported: "#2563eb", hse_event_type: "#dc2626", stop_work_flag: "#dc2626", equipment_deployed: "#4d7c0f", shift: "#475569",
  permit_status: "#dc2626", material_consumed: "#a16207",
};

/** Highlights spans (absolute offsets into `full`) inside the sentence [s0,s1). */
export function SpanHighlight({ full, sentenceSpan, spans, active, onHover }: {
  full: string; sentenceSpan: number[]; spans: Record<string, number[]>; active?: string | null; onHover?: (f: string | null) => void;
}) {
  const [s0, s1] = sentenceSpan?.length === 2 ? sentenceSpan : [0, full.length];
  const items = Object.entries(spans || {})
    .filter(([f, sp]) => f !== "cause_text" && sp && sp[0] >= s0 && sp[1] <= s1 && sp[1] > sp[0])
    .sort((a, b) => a[1][0] - b[1][0] || b[1][1] - a[1][1]);
  const parts: React.ReactNode[] = [];
  let pos = s0;
  for (const [f, [a, b]] of items) {
    if (a < pos) continue; // skip overlaps (keep the first / longest)
    if (a > pos) parts.push(full.slice(pos, a));
    const c = FIELD_COLOR[f] || "#64748b";
    parts.push(
      <mark key={f + a} className={cn("span cursor-help", active === f && "ring-2")}
        style={{ background: c + "26", color: "inherit", boxShadow: `inset 0 -2px 0 ${c}`, ["--tw-ring-color" as any]: c }}
        title={f} onMouseEnter={() => onHover?.(f)} onMouseLeave={() => onHover?.(null)}>
        {full.slice(a, b)}
      </mark>
    );
    pos = b;
  }
  if (pos < s1) parts.push(full.slice(pos, s1));
  return <span className="leading-8">{parts}</span>;
}

export function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] muted">
      {items.map(([n, c]) => (
        <span key={n} className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{n}</span>
      ))}
    </div>
  );
}
