import "leaflet/dist/leaflet.css";
import {
  Bell, BookOpen, CalendarRange, ClipboardList, FileText, Gauge, History, Inbox, Moon, Search, Settings2, ShieldAlert, Sun, Volume2, VolumeX, Waypoints,
} from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { Select, Toast } from "@/components/ui";
import { api } from "@/lib/api";
import { beep, useLive } from "@/lib/live";
import { useSession } from "@/lib/role";
import { cn } from "@/lib/utils";
import AskPage from "./Ask";
import AuditPage from "./Audit";
import DocsPage from "./Docs";
import { EventDetail, EventsPage } from "./Events";
import HSEPage from "./HSE";
import Overview from "./Overview";
import ReviewPage from "./Review";
import SchedulePage from "./Schedule";
import SettingsPage from "./Settings";
import UnplannedPage from "./Unplanned";

type Ctx = {
  meta: any; tick: number; discipline: string; setDiscipline: (d: string) => void; notify: (m: string, tone?: "teal" | "red" | "green") => void;
  reloadMeta: () => void;
};
const C = createContext<Ctx>(null as any);
export const useControl = () => useContext(C);

const NAV = [
  ["", "Overview", Gauge], ["review", "Review queue", Inbox], ["hse", "HSE Centre", ShieldAlert], ["unplanned", "Unplanned work", Waypoints],
  ["schedule", "Schedule", CalendarRange], ["events", "Event explorer", ClipboardList], ["ask", "Ask the project", Search],
  ["docs", "DPR & uploads", FileText], ["audit", "Audit trail", History], ["settings", "Settings", Settings2],
] as const;

export default function ControlApp() {
  const sess = useSession();
  const nav = useNavigate();
  const [meta, setMeta] = useState<any>(null);
  const [tick, setTick] = useState(0);
  const [discipline, setDiscipline] = useState("");
  const [toast, setToast] = useState<{ m: string; tone?: any } | null>(null);
  const [alert, setAlert] = useState<any>(null);
  const [hseOpen, setHseOpen] = useState(0);
  const [sound, setSound] = useState(localStorage.getItem("sound") !== "0");
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));

  const reloadMeta = useCallback(() => api("/api/meta").then(setMeta), []);
  const loadHse = useCallback(() => api("/api/hse").then((r: any[]) => setHseOpen(r.filter((h) => h.status !== "closed").length)), []);
  useEffect(() => { reloadMeta(); loadHse(); }, []);
  useLive((m) => {
    if (m.kind === "hse") {
      setAlert(m.data);
      loadHse();
      if (localStorage.getItem("sound") !== "0") beep();
    }
    if (m.kind === "hse_update") loadHse();
    if (["event", "schedule", "review", "report", "hse"].includes(m.kind)) setTick((t) => t + 1);
  });
  const notify = (m: string, tone?: any) => setToast({ m, tone });
  const toggleDark = () => {
    const d = !dark;
    setDark(d);
    document.documentElement.classList.toggle("dark", d);
    localStorage.setItem("theme", d ? "dark" : "light");
  };

  return (
    <C.Provider value={{ meta, tick, discipline, setDiscipline, notify, reloadMeta }}>
      <div className="flex min-h-full">
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r hairline bg-[var(--panel)] md:flex">
          <Link to="/" className="flex items-center gap-2 px-4 py-4">
            <img src="/icon.svg" className="h-7 w-7" alt="" />
            <div><div className="text-sm font-bold">SiteSync</div><div className="text-[10px] muted">Control Room</div></div>
          </Link>
          <nav className="flex-1 space-y-0.5 px-2">
            {NAV.map(([to, label, Icon]) => (
              <NavLink key={to} end={to === ""} to={`/control/${to}`}
                className={({ isActive }) => cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm", isActive ? "bg-teal-700 text-white" : "hover:bg-[var(--panel-2)]",
                  to === "hse" && !isActive && hseOpen ? "text-red-600" : "")}>
                <Icon className="h-4 w-4" /> {label}
                {to === "hse" && hseOpen > 0 && <span className="ml-auto rounded-full bg-red-600 px-1.5 text-[10px] font-bold text-white">{hseOpen}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="space-y-1 border-t hairline p-3 text-xs">
            <Link to="/field" className="block muted hover:underline">→ Field App</Link>
            <Link to="/field/whatsapp" className="block muted hover:underline">→ WhatsApp simulator</Link>
            <a href="/api/docs" target="_blank" className="flex items-center gap-1 muted hover:underline"><BookOpen className="h-3 w-3" /> API docs</a>
          </div>
        </aside>
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-[500] flex flex-wrap items-center gap-3 border-b hairline bg-[var(--panel)]/95 px-4 py-2 backdrop-blur">
            <div className="text-sm">
              <div className="font-semibold">{meta?.project?.name || "…"}</div>
              <div className="text-[11px] muted">Project date {meta?.today} · look-ahead {meta?.settings?.lookahead_days_ahead ?? 14} d · KG {meta?.kg?.nodes} nodes / {meta?.kg?.edges} edges · LLM {meta?.llm_available ? "on" : "off (rule extractor)"}</div>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Select value={discipline} onChange={(e) => setDiscipline(e.target.value)}>
                <option value="">All disciplines</option>
                {(meta?.disciplines || []).map((d: string) => <option key={d}>{d}</option>)}
              </Select>
              <button onClick={() => { setSound(!sound); localStorage.setItem("sound", sound ? "0" : "1"); }} className="rounded-lg p-2 hover:bg-[var(--panel-2)]" title="HSE alert sound">
                {sound ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
              </button>
              <button onClick={() => nav("/control/hse")} className={cn("relative rounded-lg p-2 hover:bg-[var(--panel-2)]", hseOpen && "text-red-600")} title="Open HSE items">
                <Bell className="h-5 w-5" />
                {hseOpen > 0 && <span className="absolute -right-0.5 -top-0.5 rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">{hseOpen}</span>}
              </button>
              <button onClick={toggleDark} className="rounded-lg p-2 hover:bg-[var(--panel-2)]">{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
              <span className="rounded-full bg-teal-700 px-2.5 py-1 text-xs font-medium text-white">{sess?.name || "Guest"} · {sess?.role || "viewer"}</span>
            </div>
          </header>
          {alert && (
            <div className="pulse-red mx-4 mt-3 flex items-start gap-3 rounded-xl bg-red-600 px-4 py-3 text-white">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-bold">HSE ALERT — {alert.kind === "permit" ? `${(alert.permit_type || "").replace("_", " ")} permit ${alert.permit_status}` : alert.severity} · {alert.work_front}</div>
                <div className="mt-0.5">“{alert.text}” — held for a human. Not synced to the schedule.</div>
              </div>
              <button onClick={() => { setAlert(null); nav("/control/hse"); }} className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-red-700">Open</button>
              <button onClick={() => setAlert(null)} className="px-1 text-lg leading-none">×</button>
            </div>
          )}
          <main className="p-4">
            {meta ? (
              <Routes>
                <Route index element={<Overview />} />
                <Route path="review" element={<ReviewPage />} />
                <Route path="hse" element={<HSEPage />} />
                <Route path="unplanned" element={<UnplannedPage />} />
                <Route path="schedule" element={<SchedulePage />} />
                <Route path="events" element={<EventsPage />} />
                <Route path="events/:id" element={<EventDetail />} />
                <Route path="ask" element={<AskPage />} />
                <Route path="docs" element={<DocsPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Routes>
            ) : <div className="muted">Loading…</div>}
          </main>
        </div>
      </div>
      <Toast msg={toast?.m ?? null} tone={toast?.tone} onClose={() => setToast(null)} />
    </C.Provider>
  );
}
