// Offline-first report queue (IndexedDB via `idb`).
// Every submission is written here FIRST (queued_at), then flushed to the server with
// exponential backoff. Photos are stored as Blobs so EXIF survives until upload.
// A dev toggle ("simulate offline") forces the queue to hold everything for the demo.
//
// Multi-tab coordination (all browser-native, no extra dependency):
//  * Only the Field App flushes — it calls startFlusher() on mount. Importing this module
//    (e.g. from the Control Room bundle) no longer starts a timer.
//  * Across Field App tabs, a Web Lock ("sitesync-queue-flush") makes exactly one tab flush
//    at a time; the others skip that tick. The server is also idempotent on client_id.
//  * A delivered item is moved from `queue` to `sent` (with the server reply) in one IDB
//    transaction and announced on a BroadcastChannel. Any Field tab — including one opened
//    later — reconciles its 📤 bubbles against `sent`, so it never stays stuck.
import { openDB, type IDBPDatabase } from "idb";
import { API } from "./api";

export type QueuedReport = {
  client_id: string;
  body: Record<string, any>;
  photos: { name: string; blob: Blob }[];
  queued_at: string;
  attempts: number;
  next_try: number;
  last_error?: string;
};
export type SentRecord = { client_id: string; text?: string; result: any; sent_at: number };

let dbp: Promise<IDBPDatabase> | null = null;
const db = () => (dbp ??= openDB("sitesync-field", 2, {
  upgrade: (d) => {
    if (!d.objectStoreNames.contains("queue")) d.createObjectStore("queue", { keyPath: "client_id" });
    if (!d.objectStoreNames.contains("sent")) d.createObjectStore("sent", { keyPath: "client_id" });
  },
  // another tab needs a newer schema: let go of this connection (it is reopened lazily on next use)
  blocking: () => { const p = dbp; dbp = null; p?.then((d) => d.close()); },
}));

const bc: BroadcastChannel | null = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("sitesync-queue") : null;

const listeners = new Set<() => void>();
export const onQueueChange = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
const notifyLocal = () => listeners.forEach((f) => f());
const emit = () => { notifyLocal(); bc?.postMessage({ type: "changed" }); };

type Sent = { item: { client_id: string; body: Record<string, any> }; result: any };
const sentListeners = new Set<(s: Sent) => void>();
export const onSent = (fn: (s: Sent) => void) => { sentListeners.add(fn); return () => { sentListeners.delete(fn); }; };

bc?.addEventListener("message", (m: MessageEvent) => {
  const d = m.data || {};
  if (d.type === "changed") notifyLocal();
  if (d.type === "sent") { sentListeners.forEach((f) => f({ item: { client_id: d.client_id, body: { text: d.text } }, result: d.result })); notifyLocal(); }
});

export const isSimOffline = () => localStorage.getItem("sim_offline") === "1";
export function setSimOffline(v: boolean) {
  localStorage.setItem("sim_offline", v ? "1" : "0");
  emit();
  if (!v) flush(true);
}
export const isOnline = () => navigator.onLine && !isSimOffline();

export async function enqueue(body: Record<string, any>, photos: { name: string; blob: Blob }[] = []): Promise<QueuedReport> {
  const item: QueuedReport = {
    client_id: crypto.randomUUID?.() ?? String(Date.now() + Math.random()),
    body, photos, queued_at: new Date().toISOString(), attempts: 0, next_try: 0,
  };
  item.body.queued_at = item.queued_at;
  item.body.client_id = item.client_id;
  await (await db()).put("queue", item);
  emit();
  return item;
}

export async function pending(): Promise<QueuedReport[]> {
  return (await db()).getAll("queue");
}

/** The server reply for an item another tab (or an earlier session) already delivered. */
export async function deliveredResult(client_id: string): Promise<SentRecord | undefined> {
  return (await db()).get("sent", client_id);
}

let flushing = false;
async function flushOnce(force: boolean): Promise<void> {
  if (flushing || !isOnline()) return;
  flushing = true;
  try {
    const d = await db();
    for (const queued of await d.getAll("queue")) {
      const item: QueuedReport | undefined = await d.get("queue", queued.client_id);   // re-read: may be gone already
      if (!item || (!force && item.next_try > Date.now())) continue;
      if (!isOnline()) break;
      try {
        const photo_ids: string[] = [];
        for (const p of item.photos) {
          const fd = new FormData();
          fd.append("file", p.blob, p.name);
          const r = await fetch(`${API}/api/field/photo`, { method: "POST", body: fd });
          if (!r.ok) throw new Error("photo upload " + r.status);
          photo_ids.push((await r.json()).photo_id);
        }
        const res = await fetch(`${API}/api/field/report`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...item.body, photo_ids: [...(item.body.photo_ids || []), ...photo_ids] }),
        });
        if (!res.ok) throw new Error("report " + res.status);
        const result = await res.json();
        const rec: SentRecord = { client_id: item.client_id, text: item.body.text, result, sent_at: Date.now() };
        const tx = d.transaction(["queue", "sent"], "readwrite");            // move queue → sent atomically
        await Promise.all([tx.objectStore("sent").put(rec), tx.objectStore("queue").delete(item.client_id), tx.done]);
        sentListeners.forEach((f) => f({ item, result }));
        bc?.postMessage({ type: "sent", client_id: item.client_id, text: item.body.text, result });
      } catch (e: any) {
        item.attempts += 1;
        item.next_try = Date.now() + Math.min(60_000, 1000 * 2 ** item.attempts); // exponential backoff, capped at 60 s
        item.last_error = String(e?.message || e);
        if (await d.get("queue", item.client_id)) await d.put("queue", item);
      }
      emit();
    }
    // keep delivered replies for a day so late-opened tabs can reconcile, then prune
    for (const s of await d.getAll("sent")) if (Date.now() - s.sent_at > 86_400_000) await d.delete("sent", s.client_id);
  } finally {
    flushing = false;
  }
}

/** Flush the queue if this tab can take the cross-tab flush lock; otherwise another tab is flushing — skip. */
export async function flush(force = false): Promise<void> {
  const locks = (navigator as any).locks;
  if (!locks?.request) return flushOnce(force);                           // very old browser: per-tab guard only
  await locks.request("sitesync-queue-flush", { ifAvailable: true }, async (lock: unknown) => { if (lock) await flushOnce(force); });
}

let started = 0;
let timer: ReturnType<typeof setInterval> | null = null;
const onOnline = () => flush(true);
/** Background retry loop + reconnect trigger. Only the Field App starts it; returns a stop function. */
export function startFlusher(): () => void {
  if (started++ === 0 && typeof window !== "undefined") {
    window.addEventListener("online", onOnline);
    timer = setInterval(() => flush(), 4000);
    flush(true);
  }
  return () => {
    if (--started === 0) {
      window.removeEventListener("online", onOnline);
      if (timer) clearInterval(timer);
      timer = null;
    }
  };
}
