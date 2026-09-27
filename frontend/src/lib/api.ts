// Thin fetch wrapper. In dev Vite proxies /api → :8000; in single-port mode FastAPI serves both.
export const API = (import.meta as any).env?.VITE_API ?? "";

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = opts;
  const res = await fetch(API + path, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...(rest.headers || {}) } : rest.headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`${res.status} ${t.slice(0, 200)}`);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export async function upload<T = any>(path: string, file: File | Blob, name = "file", extra: Record<string, string> = {}): Promise<T> {
  const fd = new FormData();
  fd.append(name, file, (file as File).name || "upload.bin");
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  const res = await fetch(API + path, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const photoUrl = (id: string) => `${API}/api/photos/${encodeURIComponent(id)}`;

export type State = "linked" | "review" | "unplanned" | "duplicate" | "unparseable" | "clarifying" | "hse_hold";

export const STATE_COLOR: Record<string, string> = {
  linked: "#16a34a", review: "#d97706", clarifying: "#f59e0b", unplanned: "#2563eb", hse_hold: "#dc2626", duplicate: "#6b7280", unparseable: "#9ca3af",
  "Auto-sync": "#16a34a", Clarify: "#f59e0b", Review: "#d97706", Unplanned: "#2563eb", "HSE hold": "#dc2626", Duplicate: "#6b7280", Unparseable: "#9ca3af",
};
// Categorical identity colours: validated fixed order (dataviz reference palette), never cycled.
export const CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
export const PATH_COLOR: Record<string, string> = { kg_narrowed: CAT[0], vector_only: CAT[1], fuzzy_fallback: CAT[2] };
export const DISC_COLOR: Record<string, string> = {
  Piping: CAT[0], Civil: CAT[1], Structural: CAT[2], Electrical: CAT[3], Instrumentation: CAT[4], Mechanical: CAT[5],
};
export const CHANNEL_COLOR: Record<string, string> = { whatsapp: CAT[0], pwa: CAT[1], telegram: CAT[2], dpr_upload: CAT[3], spreadsheet: CAT[4] };
export const PROV_COLOR: Record<string, string> = { GIVEN: "#475569", EXTRACTED: "#7c3aed", FETCHED: "#0284c7", DERIVED: "#0f766e", HUMAN: "#c2410c" };

export const fmtDate = (d?: string | null) => (d ? new Date(d + (d.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) : "—");
export const fmtTime = (d?: string | null) => (d ? new Date(d).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export const pct = (v?: number | null) => (v == null ? "—" : `${Math.round(v * 100)}`);
