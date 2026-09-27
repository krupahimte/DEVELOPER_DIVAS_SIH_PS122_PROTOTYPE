// Field App state: who am I, GPS (real or demo-simulated), the offline queue, and the chat thread.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { deliveredResult, enqueue, flush, isOnline, isSimOffline, onQueueChange, onSent, pending, startFlusher, type QueuedReport } from "@/lib/offlineQueue";
import { useSession } from "@/lib/role";

export type Bubble = {
  id: string; who: "me" | "bot"; text: string; at: string; status?: "queued" | "sent"; photo?: string;
  question?: { event_id: number; question: string; question_hi?: string; options: { label: string; label_hi?: string; value: string }[] } | null;
  answered?: string; clientId?: string; echoOf?: string;
};

export type GpsMode = string; // "real" | "none" | "weak" | "zone:WF-…"

type Ctx = {
  me: any; fronts: any[]; userId: string;
  online: boolean; queued: QueuedReport[];
  gpsMode: GpsMode; setGpsMode: (m: GpsMode) => void;
  backdateH: number; setBackdateH: (h: number) => void;
  thread: Bubble[]; pushBubble: (b: Bubble) => void; updateBubble: (id: string, patch: Partial<Bubble>) => void;
  submit: (body: Record<string, any>, photos?: { name: string; blob: Blob }[], echo?: string) => Promise<void>;
  answer: (b: Bubble, value: string, label: string) => Promise<void>;
};

const FieldCtx = createContext<Ctx>(null as any);
export const useField = () => useContext(FieldCtx);

async function getGps(mode: GpsMode, fronts: any[]): Promise<{ gps_lat?: number; gps_lon?: number; gps_accuracy?: number; gps_timestamp?: string }> {
  const now = new Date().toISOString();
  if (mode === "none") return {};
  if (mode === "real") {
    return new Promise((res) => {
      if (!navigator.geolocation) return res({});
      navigator.geolocation.getCurrentPosition(
        (p) => res({ gps_lat: p.coords.latitude, gps_lon: p.coords.longitude, gps_accuracy: p.coords.accuracy, gps_timestamp: now }),
        () => res({}), { timeout: 4000, maximumAge: 60000 });
    });
  }
  if (mode === "weak") return { gps_lat: 27.4743, gps_lon: 95.33805, gps_accuracy: 80, gps_timestamp: now }; // between Rack B and Rack C
  const wfId = mode.startsWith("zone:") ? mode.slice(5) : fronts[0]?.id;
  const w = fronts.find((f) => f.id === wfId) || (window as any).__allFronts?.find((f: any) => f.id === wfId);
  if (!w) return {};
  const j = () => (Math.random() - 0.5) * 0.00012;
  return { gps_lat: w.lat + j(), gps_lon: w.lon + j(), gps_accuracy: 8, gps_timestamp: now };
}

export function FieldProvider({ children }: { children: React.ReactNode }) {
  const sess = useSession();
  const userId = sess?.role === "field" ? sess.user : "R-KALITA";
  const [me, setMe] = useState<any>(null);
  const [fronts, setFronts] = useState<any[]>([]);
  const [online, setOnline] = useState(isOnline());
  const [queued, setQueued] = useState<QueuedReport[]>([]);
  const [gpsMode, setGpsModeS] = useState<GpsMode>(() => localStorage.getItem("gps_mode_" + userId) || "zone");
  const [backdateH, setBackdateH] = useState(0);
  const key = "thread_" + userId;
  const [thread, setThread] = useState<Bubble[]>(() => { try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch { return []; } });
  const threadRef = useRef(thread);
  threadRef.current = thread;

  useEffect(() => {
    api(`/api/field/me?reporter_id=${userId}`).then((d) => { setMe(d.reporter); setFronts(d.work_fronts); }).catch(() => {});
    api("/api/meta").then((m) => ((window as any).__allFronts = m.work_fronts)).catch(() => {});
  }, [userId]);
  useEffect(() => { localStorage.setItem(key, JSON.stringify(thread.slice(-80))); }, [thread]);

  // Mark a delivered report's bubble sent and add the bot reply — once, and only for bubbles in THIS thread
  // (the delivery may have been made by another tab, and announced over BroadcastChannel / found in IDB).
  const applySent = useCallback((clientId: string, echo: string | undefined, result: any) => {
    setThread((t) => {
      if (!t.some((b) => b.clientId === clientId)) return t;
      const lang = localStorage.getItem("lang") || "hi";
      const out = t.map((b) => (b.clientId === clientId && b.status !== "sent" ? { ...b, status: "sent" as const } : b));
      if (!out.some((b) => b.id === "r" + clientId)) {
        const reply = result?.reply || {};
        const txt = (lang === "hi" ? reply.hi : reply.en) || reply.en || "✅";
        out.push({ id: "r" + clientId, who: "bot", text: txt, at: new Date().toISOString(), question: reply.question || null, echoOf: echo });
      }
      return out;
    });
  }, []);

  // Any 📤 bubble no longer in the queue was delivered (possibly by another tab): pick up its stored reply.
  const reconcile = useCallback(async (q: QueuedReport[]) => {
    const inQueue = new Set(q.map((i) => i.client_id));
    for (const b of threadRef.current) {
      if (b.who !== "me" || b.status !== "queued" || !b.clientId || inQueue.has(b.clientId)) continue;
      const rec = await deliveredResult(b.clientId);
      if (rec) applySent(b.clientId, rec.text, rec.result);
    }
  }, [applySent]);

  const refresh = useCallback(async () => { const q = await pending(); setQueued(q); setOnline(isOnline()); reconcile(q); }, [reconcile]);
  useEffect(() => startFlusher(), []);
  useEffect(() => {
    refresh();
    const off1 = onQueueChange(refresh);
    const onl = () => refresh();
    window.addEventListener("online", onl);
    window.addEventListener("offline", onl);
    return () => { off1(); window.removeEventListener("online", onl); window.removeEventListener("offline", onl); };
  }, [refresh]);

  const pushBubble = useCallback((b: Bubble) => setThread((t) => [...t, b]), []);
  const updateBubble = useCallback((id: string, patch: Partial<Bubble>) => setThread((t) => t.map((b) => (b.id === id ? { ...b, ...patch } : b))), []);

  // when the queue delivers a report (this tab or another), mark the bubble sent and show the bot reply
  useEffect(() => onSent(({ item, result }) => applySent(item.client_id, item.body?.text, result)), [applySent]);

  const setGpsMode = (m: GpsMode) => { setGpsModeS(m); localStorage.setItem("gps_mode_" + userId, m); };

  const submit = useCallback(async (body: Record<string, any>, photos: { name: string; blob: Blob }[] = []) => {
    const cap = new Date(Date.now() - backdateH * 3600_000).toISOString();
    const gps = await getGps(gpsMode === "zone" ? `zone:${fronts[0]?.id}` : gpsMode, fronts);
    const full = { reporter_id: userId, channel: "pwa", captured_at: cap, device_id: "android-" + userId.slice(2, 6).toLowerCase() + "-01",
                   app_version: "pwa-1.4.2", ...gps, ...body };
    const item = await enqueue(full, photos);
    pushBubble({ id: "m" + item.client_id, who: "me", text: body.text || (photos.length ? "📷" : "…"), at: cap, status: "queued", clientId: item.client_id,
                 photo: photos[0] ? URL.createObjectURL(photos[0].blob) : undefined });
    flush(true);
  }, [userId, gpsMode, fronts, backdateH, pushBubble]);

  const answer = useCallback(async (b: Bubble, value: string, label: string) => {
    if (!b.question) return;
    updateBubble(b.id, { answered: label });
    pushBubble({ id: "a" + Date.now(), who: "me", text: label, at: new Date().toISOString(), status: "sent" });
    try {
      const r = await api("/api/field/clarify", { method: "POST", json: { event_id: b.question.event_id, value } });
      const lang = localStorage.getItem("lang") || "hi";
      pushBubble({ id: "ra" + Date.now(), who: "bot", text: (lang === "hi" ? r.reply.hi : r.reply.en) || r.reply.en, at: new Date().toISOString() });
    } catch {
      pushBubble({ id: "ra" + Date.now(), who: "bot", text: "⚠️ No signal — please answer again when online.", at: new Date().toISOString() });
      updateBubble(b.id, { answered: undefined });
    }
  }, [pushBubble, updateBubble]);

  const value = useMemo(() => ({ me, fronts, userId, online, queued, gpsMode, setGpsMode, backdateH, setBackdateH, thread, pushBubble, updateBubble, submit, answer }),
    [me, fronts, userId, online, queued, gpsMode, backdateH, thread, pushBubble, updateBubble, submit, answer]);
  return <FieldCtx.Provider value={value}>{children}</FieldCtx.Provider>;
}

export const simOffline = isSimOffline;
