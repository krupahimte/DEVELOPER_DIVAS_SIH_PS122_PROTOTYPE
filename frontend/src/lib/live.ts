// Live updates from the server (SSE): schedule writes, HSE alerts, review decisions.
import { useEffect, useRef } from "react";
import { API } from "./api";

export type LiveMsg = { kind: string; data: any };

export function useLive(onMsg: (m: LiveMsg) => void) {
  const ref = useRef(onMsg);
  ref.current = onMsg;
  useEffect(() => {
    let es: EventSource | null = null;
    let stop = false;
    const open = () => {
      es = new EventSource(`${API}/api/stream`);
      es.onmessage = (ev) => {
        try {
          ref.current(JSON.parse(ev.data));
        } catch {
          /* ping */
        }
      };
      es.onerror = () => {
        es?.close();
        if (!stop) setTimeout(open, 3000);
      };
    };
    open();
    return () => {
      stop = true;
      es?.close();
    };
  }, []);
}

// Short synthetic "ding" for HSE alerts (no audio file needed).
export function beep() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "square";
    o.frequency.value = 880;
    g.gain.value = 0.08;
    o.connect(g);
    g.connect(ctx.destination);
    o.start();
    setTimeout(() => { o.frequency.value = 660; }, 180);
    setTimeout(() => { o.stop(); ctx.close(); }, 420);
  } catch {
    /* no audio */
  }
}
