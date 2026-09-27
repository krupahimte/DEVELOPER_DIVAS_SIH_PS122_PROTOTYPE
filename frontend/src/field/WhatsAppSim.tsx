// WhatsApp simulator: a phone-frame chat that posts to the same ingest endpoint with channel="whatsapp".
// Like real WhatsApp there is no GPS; photos are sent as files (real WhatsApp strips EXIF).
import { ArrowLeft, Camera, CheckCheck, Mic, MoreVertical, Paperclip, Phone, Send, Video } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, photoUrl } from "@/lib/api";
import { useSession } from "@/lib/role";
import { cn } from "@/lib/utils";

type Msg = { id: string; who: "me" | "bot"; text: string; at: string; photo?: string; question?: any; answered?: string };

const SUGGEST = [
  "Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder",
  "spool erected near rack",
  "Welding started Rack C",
  "Spool 5 erected",
  "Work stopped due to rain from 2pm",
  "Laid temporary drainage near U3 gate",
  "Near miss, sling slipped at crane CR-50T-02",
];

export default function WhatsAppSim() {
  const sess = useSession();
  const [reps, setReps] = useState<any[]>([]);
  const [who, setWho] = useState(sess?.role === "field" ? sess.user : "R-KALITA");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api("/api/meta").then((m) => setReps(m.reporters.filter((r: any) => ["supervisor", "foreman"].includes(r.role)))); }, []);
  useEffect(() => {
    api(`/api/field/thread?reporter_id=${who}&channel=whatsapp`).then((rows: any[]) => {
      const out: Msg[] = [];
      for (const r of rows) {
        out.push({ id: "m" + r.report_id, who: "me", text: r.text, at: r.at, photo: r.photos?.[0] ? photoUrl(r.photos[0]) : undefined });
        out.push({ id: "b" + r.report_id, who: "bot", text: r.reply.en, at: r.at, question: r.reply.question });
      }
      setMsgs(out);
    });
  }, [who]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);

  const send = async (t = text, photo?: File) => {
    if (!t.trim() && !photo) return;
    setBusy(true);
    const now = new Date().toISOString();
    const local: Msg = { id: "l" + Date.now(), who: "me", text: t, at: now, photo: photo ? URL.createObjectURL(photo) : undefined };
    setMsgs((m) => [...m, local]);
    setText("");
    try {
      let photo_ids: string[] = [];
      if (photo) {
        const fd = new FormData();
        fd.append("file", photo, photo.name);
        photo_ids = [(await (await fetch("/api/field/photo", { method: "POST", body: fd })).json()).photo_id];
      }
      const r = await api("/api/field/report", { method: "POST", json: { text: t, reporter_id: who, channel: "whatsapp", source_type: "whatsapp", captured_at: now, photo_ids } });
      setMsgs((m) => [...m, { id: "b" + r.report_id, who: "bot", text: r.reply.en, at: new Date().toISOString(), question: r.reply.question }]);
    } finally {
      setBusy(false);
    }
  };
  const answer = async (m: Msg, value: string, label: string) => {
    setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, answered: label } : x)).concat({ id: "a" + Date.now(), who: "me", text: label, at: new Date().toISOString() }));
    const r = await api("/api/field/clarify", { method: "POST", json: { event_id: m.question.event_id, value } });
    setMsgs((all) => [...all, { id: "ba" + Date.now(), who: "bot", text: r.reply.en, at: new Date().toISOString() }]);
  };
  const me = reps.find((r) => r.id === who);

  return (
    <div className="flex min-h-full flex-col items-center gap-4 bg-gradient-to-br from-slate-200 to-slate-300 p-4 dark:from-slate-900 dark:to-slate-950 md:flex-row md:items-start md:justify-center md:p-8">
      <div className="w-full max-w-[380px] shrink-0 overflow-hidden rounded-[42px] border-[10px] border-slate-900 bg-[#efeae2] shadow-2xl">
        <div className="flex items-center gap-2 bg-[#008069] px-3 py-2.5 text-white">
          <Link to="/" className="p-1"><ArrowLeft className="h-5 w-5" /></Link>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-lg">🏗️</div>
          <div className="flex-1 leading-tight">
            <div className="font-semibold">SiteSync Bot</div>
            <div className="text-[11px] text-white/80">{busy ? "typing…" : "online"}</div>
          </div>
          <Video className="h-5 w-5" /><Phone className="h-5 w-5" /><MoreVertical className="h-5 w-5" />
        </div>
        <div className="h-[560px] space-y-1.5 overflow-y-auto p-3" style={{ backgroundImage: "radial-gradient(#d6cfc4 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
          <div className="mx-auto w-fit rounded-md bg-[#fff5c4] px-2 py-1 text-center text-[11px] text-slate-700">🔒 Messages go to the project schedule. Safety items go to the HSE officer.</div>
          {msgs.map((m) => (
            <div key={m.id} className={cn("flex", m.who === "me" ? "justify-end" : "justify-start")}>
              <div className={cn("max-w-[82%] rounded-lg px-2.5 py-1.5 text-[14px] shadow-sm", m.who === "me" ? "bg-[#d9fdd3]" : "bg-white")}>
                {m.photo && <img src={m.photo} className="mb-1 max-h-40 rounded" alt="" />}
                <div className="whitespace-pre-wrap text-slate-900">{m.text}</div>
                {m.question && (
                  <div className="mt-1.5 space-y-1">
                    {m.question.options.map((o: any) => (
                      <button key={o.value} disabled={!!m.answered} onClick={() => answer(m, o.value, o.label)}
                        className={cn("block w-full rounded-md border px-2 py-1.5 text-center text-[14px] font-medium text-[#008069]", m.answered === o.label ? "border-[#008069] bg-[#008069]/10" : "border-slate-200 disabled:opacity-40")}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-slate-500">
                  {m.at ? new Date(m.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                  {m.who === "me" && <CheckCheck className="h-3.5 w-3.5 text-sky-500" />}
                </div>
              </div>
            </div>
          ))}
          <div ref={end} />
        </div>
        <div className="flex items-center gap-1.5 bg-[#f0f2f5] p-2">
          <div className="flex flex-1 items-center gap-2 rounded-full bg-white px-3">
            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Message"
              className="h-10 min-w-0 flex-1 bg-transparent text-[15px] text-slate-900 outline-none" />
            <button onClick={() => fileRef.current?.click()}><Paperclip className="h-5 w-5 text-slate-500" /></button>
            <Camera className="h-5 w-5 text-slate-500" />
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && send(text || "", e.target.files[0])} />
          </div>
          <button onClick={() => send()} className="flex h-10 w-10 items-center justify-center rounded-full bg-[#008069] text-white">
            {text.trim() ? <Send className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          </button>
        </div>
      </div>
      <div className="w-full max-w-sm space-y-3 text-sm">
        <div className="rounded-xl bg-white p-4 shadow dark:bg-slate-800">
          <div className="font-semibold">WhatsApp simulator</div>
          <p className="mt-1 text-slate-600 dark:text-slate-300">Same pipeline as the PWA, <code>channel="whatsapp"</code>, no GPS (WhatsApp doesn't send it), so verification relies on the reporter's assigned work front.</p>
          <label className="mt-3 block text-xs text-slate-500">Sending as</label>
          <select value={who} onChange={(e) => setWho(e.target.value)} className="mt-1 w-full rounded-lg border px-2 py-1.5 dark:bg-slate-900">
            {reps.map((r) => <option key={r.id} value={r.id}>{r.name} · {r.discipline}</option>)}
          </select>
          {me && <div className="mt-1 text-xs text-slate-500">Work fronts: {(me.work_fronts || []).join(", ")}</div>}
        </div>
        <div className="rounded-xl bg-white p-4 shadow dark:bg-slate-800">
          <div className="mb-2 font-semibold">Try (demo script)</div>
          <div className="space-y-1.5">
            {SUGGEST.map((s) => <button key={s} onClick={() => send(s)} className="block w-full rounded-lg bg-slate-100 px-2 py-1.5 text-left hover:bg-slate-200 dark:bg-slate-900">{s}</button>)}
          </div>
        </div>
        <Link to="/control" className="block text-center text-teal-700 underline">Open Control Room →</Link>
      </div>
    </div>
  );
}
