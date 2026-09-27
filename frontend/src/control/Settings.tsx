// Settings: gate thresholds (live), clarification cap, channels, LLM, weather source, demo reset.
import { RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Card, CardHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useControl } from "./ControlApp";

const SLIDERS: [string, string][] = [
  ["extraction", "Extraction ≥"], ["match", "Match ≥"], ["date", "Date ≥"], ["verification", "Verification ≥ (start/progress)"],
  ["verification_finish", "Verification ≥ (finish claims)"], ["margin", "Match margin ≥"], ["borderline_band", "Borderline band (clarify)"],
  ["clarify_top2_min", "Clarify when top-2 both ≥"], ["candidate_min", "Unplanned when no candidate ≥"],
];

export default function SettingsPage() {
  const { meta, reloadMeta, notify } = useControl();
  const [s, setS] = useState<any>(meta.settings);
  const [resetting, setResetting] = useState(false);
  useEffect(() => { setS(meta.settings); }, [meta.settings]);
  const save = async (patch: any) => { const r = await api("/api/settings", { method: "PUT", json: patch }); setS(r); reloadMeta(); };
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader title="Four-number gate" subtitle="Applied live to every new event. Auto-sync needs ALL four above threshold and a wide margin — never an average." />
        <div className="space-y-3 px-4 pb-4">
          {SLIDERS.map(([k, label]) => (
            <label key={k} className="block">
              <div className="flex justify-between text-sm"><span>{label}</span><span className="font-mono">{s.gate[k].toFixed(2)}</span></div>
              <input type="range" min={0} max={k === "margin" || k === "borderline_band" ? 0.5 : 1} step={0.01} value={s.gate[k]}
                onChange={(e) => setS({ ...s, gate: { ...s.gate, [k]: +e.target.value } })} onMouseUp={() => save({ gate: s.gate })} onTouchEnd={() => save({ gate: s.gate })}
                className="w-full accent-teal-700" />
            </label>
          ))}
          <Button variant="outline" onClick={() => save({ gate: { extraction: 0.85, match: 0.85, date: 0.8, verification: 0.7, verification_finish: 0.85, margin: 0.1, borderline_band: 0.15, clarify_top2_min: 0.7, candidate_min: 0.5 } })}>Restore defaults</Button>
        </div>
      </Card>
      <div className="space-y-4">
        <Card>
          <CardHeader title="Behaviour" />
          <div className="space-y-3 px-4 pb-4 text-sm">
            <label className="flex items-center justify-between">Clarifying questions per report (cap)
              <Select value={s.clarification_cap} onChange={(e) => save({ clarification_cap: +e.target.value })}><option value={0}>0 (never ask)</option><option value={1}>1 (spec)</option></Select></label>
            <label className="flex items-center justify-between">LLM extraction (Claude) {meta.llm_available ? "" : <span className="text-xs muted">— no API key; rule extractor in use</span>}
              <input type="checkbox" checked={s.llm_enabled} onChange={(e) => save({ llm_enabled: e.target.checked })} className="h-5 w-5 accent-teal-700" /></label>
            <label className="flex items-center justify-between">Weather source
              <Select value={s.weather_mode} onChange={(e) => save({ weather_mode: e.target.value })}>
                <option value="seeded_first">Site station seed, then Open-Meteo</option><option value="live_first">Open-Meteo, then seed</option><option value="seeded_only">Seed only (offline)</option>
              </Select></label>
            <label className="flex items-center justify-between">Look-ahead window (days ahead)
              <input type="number" value={s.lookahead_days_ahead} onChange={(e) => save({ lookahead_days_ahead: +e.target.value })} className="w-20 rounded border hairline bg-transparent px-2 py-1" /></label>
            <div className="pt-1 font-medium">Enabled channels</div>
            <div className="flex flex-wrap gap-3">{Object.entries(s.channels).map(([k, v]: any) => (
              <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={v} onChange={(e) => save({ channels: { [k]: e.target.checked } })} className="accent-teal-700" />{k}</label>))}</div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Demo" subtitle="Rebuild the site: master data + 3 weeks of history replayed through the pipeline (~10 s)." />
          <div className="px-4 pb-4">
            <Button variant="danger" disabled={resetting} onClick={async () => { setResetting(true); try { const r = await api("/api/admin/reset", { method: "POST" }); notify(`Demo reset: ${r.reports} reports replayed`, "green"); reloadMeta(); localStorage.removeItem("thread_R-KALITA"); } finally { setResetting(false); } }}>
              <RotateCcw className="h-4 w-4" />{resetting ? "Resetting…" : "Reset demo"}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
