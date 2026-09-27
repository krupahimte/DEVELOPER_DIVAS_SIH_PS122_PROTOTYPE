// Demo "login": role + user picked on the landing page (no real auth; seeded users).
import { useSyncExternalStore } from "react";

export type Session = { role: "field" | "planner" | "hse" | "pm"; user: string; name: string };

const KEY = "sitesync_session";
const subs = new Set<() => void>();
let cur: Session | null = (() => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null");
  } catch {
    return null;
  }
})();

export function setSession(s: Session | null) {
  cur = s;
  if (s) localStorage.setItem(KEY, JSON.stringify(s));
  else localStorage.removeItem(KEY);
  subs.forEach((f) => f());
}
export const useSession = () => useSyncExternalStore((cb) => (subs.add(cb), () => subs.delete(cb)), () => cur);
