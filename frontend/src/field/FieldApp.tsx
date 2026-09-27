import { ArrowLeft, Bug, Globe, Wifi, WifiOff } from "lucide-react";
import { useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { setSimOffline } from "@/lib/offlineQueue";
import { setLang, useLang } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Chat, Home, MyReports, PhotoNote, Problem, Safety } from "./screens";
import { FieldProvider, useField } from "./useField";

export default function FieldApp() {
  return (
    <FieldProvider>
      <div className="field-root min-h-full bg-slate-100 dark:bg-slate-950 md:py-6">
        <div className="relative mx-auto flex min-h-[100dvh] max-w-md flex-col bg-white shadow-2xl md:min-h-[calc(100dvh-3rem)] md:rounded-[28px] md:ring-8 md:ring-slate-800 dark:bg-slate-900">
          <Header />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route index element={<Home />} />
              <Route path="chat" element={<Chat />} />
              <Route path="photo" element={<PhotoNote />} />
              <Route path="problem" element={<Problem />} />
              <Route path="safety" element={<Safety />} />
              <Route path="reports" element={<MyReports />} />
            </Routes>
          </main>
        </div>
        <DevPanel />
      </div>
    </FieldProvider>
  );
}

function Header() {
  const { me, online, queued } = useField();
  const [lang, t] = useLang();
  const loc = useLocation();
  const nav = useNavigate();
  const home = loc.pathname === "/field" || loc.pathname === "/field/";
  return (
    <header className="sticky top-0 z-10 rounded-t-[inherit] bg-teal-800 px-4 pb-3 pt-4 text-white">
      <div className="flex items-center justify-between">
        {home ? (
          <Link to="/" className="text-xs text-teal-100/80">SiteSync</Link>
        ) : (
          <button onClick={() => nav("/field")} className="tap -ml-2 flex items-center gap-1 rounded-lg px-2 text-base"><ArrowLeft className="h-5 w-5" /> {t("back")}</button>
        )}
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-white/15 px-2 py-0.5 text-xs">{me?.name || "…"}</span>
          <button onClick={() => setLang(lang === "hi" ? "en" : "hi")} className="flex h-10 items-center gap-1 rounded-full bg-white px-3 text-sm font-bold text-teal-800">
            <Globe className="h-4 w-4" /> {lang === "hi" ? "EN" : "हिं"}
          </button>
        </div>
      </div>
      <div className={cn("mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium", online ? "bg-green-600/90" : "bg-amber-500 text-slate-900")}>
        {online ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
        {online ? (queued.length ? t("sending", { n: queued.length }) : t("online")) : t("offlineWaiting", { n: queued.length })}
      </div>
    </header>
  );
}

/** Demo-only controls (not part of the worker UI): simulate offline, GPS quality, backdated capture. */
function DevPanel() {
  const { online, gpsMode, setGpsMode, backdateH, setBackdateH, fronts, queued } = useField();
  const [open, setOpen] = useState(false);
  const all = (window as any).__allFronts || fronts;
  return (
    <div className="fixed bottom-3 right-3 z-50 text-sm">
      {open && (
        <div className="mb-2 w-72 rounded-xl bg-slate-900 p-3 text-slate-100 shadow-2xl ring-1 ring-slate-700">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Demo controls</div>
          <label className="flex items-center justify-between py-1">
            <span>Simulate offline</span>
            <input type="checkbox" checked={!online} onChange={(e) => setSimOffline(e.target.checked)} className="h-5 w-5" />
          </label>
          <div className="text-xs text-slate-400">Queue: {queued.length} waiting</div>
          <label className="mt-2 block">
            <span className="text-xs text-slate-400">GPS</span>
            <select value={gpsMode} onChange={(e) => setGpsMode(e.target.value)} className="mt-1 w-full rounded bg-slate-800 px-2 py-1.5">
              <option value="zone">At my work front (good fix)</option>
              {all.map((w: any) => <option key={w.id} value={`zone:${w.id}`}>At {w.name} ({w.unit})</option>)}
              <option value="weak">Weak signal ±80 m (between Rack B/C)</option>
              <option value="none">No GPS</option>
              <option value="real">Real device GPS</option>
            </select>
          </label>
          <label className="mt-2 block">
            <span className="text-xs text-slate-400">Captured … hours ago (offline demo)</span>
            <input type="number" min={0} max={48} value={backdateH} onChange={(e) => setBackdateH(+e.target.value)} className="mt-1 w-full rounded bg-slate-800 px-2 py-1.5" />
          </label>
          <div className="mt-2 flex gap-2 text-xs">
            <Link className="underline" to="/field/whatsapp">WhatsApp sim</Link>
            <Link className="underline" to="/control">Control Room</Link>
          </div>
        </div>
      )}
      <button onClick={() => setOpen(!open)} className="ml-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-white shadow-lg" title="Demo controls">
        <Bug className="h-5 w-5" />
      </button>
    </div>
  );
}
