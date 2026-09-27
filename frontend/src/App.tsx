import { HardHat, LayoutDashboard, ShieldAlert, ClipboardCheck, MessageCircle } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import FieldApp from "./field/FieldApp";
import WhatsAppSim from "./field/WhatsAppSim";
import { api } from "./lib/api";
import { setSession, useSession, type Session } from "./lib/role";

// Charts + maps are only for the Control Room: keep them out of the Field App bundle (cheap phones, weak signal).
const ControlApp = lazy(() => import("./control/ControlApp"));

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/field/whatsapp" element={<WhatsAppSim />} />
      <Route path="/field/*" element={<FieldApp />} />
      <Route path="/control/*" element={<Suspense fallback={<div className="p-8 muted">Loading Control Room…</div>}><ControlApp /></Suspense>} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

function Landing() {
  const nav = useNavigate();
  const sess = useSession();
  const [reps, setReps] = useState<any[]>([]);
  useEffect(() => { api("/api/meta").then((m) => setReps(m.reporters)).catch(() => {}); }, []);
  const go = (s: Session, path: string) => { setSession(s); nav(path); };
  const field = reps.filter((r) => ["supervisor", "foreman"].includes(r.role));
  const byRole = (role: string) => reps.find((r) => r.role === role);
  return (
    <div className="min-h-full bg-gradient-to-b from-teal-900 to-slate-900 px-4 py-10 text-white">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center gap-3">
          <img src="/icon.svg" className="h-10 w-10" alt="" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">SiteSync</h1>
            <p className="text-sm text-teal-100/80">Field progress → schedule actuals · Refinery Expansion, Assam · SIH PS 122 prototype</p>
          </div>
        </div>
        <p className="mt-6 max-w-3xl text-teal-50/90">
          Supervisors report the way they already do — WhatsApp, voice, photos, DPRs. Each input becomes field <b>events</b>, matched to
          L5/L6 activities through a knowledge graph, gated by <b>four separate confidences + a match margin</b>, and written back as
          actual start / finish dates — or routed to one question, one planner tap, or unplanned work. Safety never auto-syncs.
        </p>
        <h2 className="mt-10 mb-3 text-sm font-semibold uppercase tracking-wider text-teal-200">Pick a role (demo users)</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/15">
            <div className="flex items-center gap-2 text-lg font-semibold"><HardHat className="h-5 w-5" /> Field App</div>
            <p className="mt-1 text-sm text-teal-50/80">Big buttons, voice first, Hindi/English, works offline.</p>
            <div className="mt-4 space-y-2">
              {field.map((r) => (
                <button key={r.id} onClick={() => go({ role: "field", user: r.id, name: r.name }, "/field")}
                  className="flex w-full items-center justify-between rounded-xl bg-white/10 px-3 py-2 text-left hover:bg-white/20">
                  <span><b>{r.name}</b> <span className="text-xs text-teal-100/70">· {r.discipline}</span></span>
                  <span className="text-[11px] text-teal-100/60">{(r.work_fronts || []).map((w: string) => w.replace("WF-", "")).join(", ")}</span>
                </button>
              ))}
            </div>
            <button onClick={() => { const r = byRole("supervisor") || field[0]; go({ role: "field", user: r?.id || "R-KALITA", name: r?.name || "S. Kalita" }, "/field/whatsapp"); }}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-green-600/90 px-3 py-2 text-sm font-medium hover:bg-green-600">
              <MessageCircle className="h-4 w-4" /> WhatsApp simulator (S. Kalita)
            </button>
          </div>
          <div className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/15">
            <div className="flex items-center gap-2 text-lg font-semibold"><LayoutDashboard className="h-5 w-5" /> Control Room</div>
            <p className="mt-1 text-sm text-teal-50/80">Graphs, review queue, schedule write-back, audit.</p>
            <div className="mt-4 space-y-2">
              {reps.filter((r) => ["planner", "pm"].includes(r.role)).map((r) => (
                <button key={r.id} onClick={() => go({ role: r.role === "pm" ? "pm" : "planner", user: r.id, name: r.name }, r.role === "pm" ? "/control" : "/control/review")}
                  className="flex w-full items-center justify-between rounded-xl bg-white/10 px-3 py-2 text-left hover:bg-white/20">
                  <span><b>{r.name}</b></span><span className="text-xs text-teal-100/70">{r.role === "pm" ? "Project manager" : `Planner · ${r.discipline}`}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/15">
            <div className="flex items-center gap-2 text-lg font-semibold"><ShieldAlert className="h-5 w-5" /> HSE Centre</div>
            <p className="mt-1 text-sm text-teal-50/80">Every safety item reaches a human — always.</p>
            <div className="mt-4 space-y-2">
              {reps.filter((r) => r.role === "hse").map((r) => (
                <button key={r.id} onClick={() => go({ role: "hse", user: r.id, name: r.name }, "/control/hse")}
                  className="flex w-full items-center justify-between rounded-xl bg-red-500/20 px-3 py-2 text-left ring-1 ring-red-300/30 hover:bg-red-500/30">
                  <span><b>{r.name}</b></span><span className="text-xs text-red-100/80">HSE officer</span>
                </button>
              ))}
            </div>
            <div className="mt-6 flex items-center gap-2 text-xs text-teal-100/70"><ClipboardCheck className="h-4 w-4" /> Demo script: DEMO_SCRIPT.md</div>
          </div>
        </div>
        {sess && <p className="mt-6 text-xs text-teal-100/60">Last used: {sess.name} ({sess.role})</p>}
      </div>
    </div>
  );
}
