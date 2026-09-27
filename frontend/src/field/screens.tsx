// Field App screens. Rules: one primary action per screen, targets ≥ 56 px, text ≥ 18 px,
// icons + words on every button, ≤ 3 inputs, no jargon.
import {
  AlertOctagon, Camera, CheckCircle2, ChevronDown, CloudRain, Clock3, FileWarning, HelpCircle, Keyboard, Mic, Minus, Package, Pencil, Plus, Send,
  ShieldAlert, Truck, Upload, Users, Wrench,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useField, type Bubble } from "./useField";
import { useSpeech } from "./useSpeech";

// ───────────────────────────── Home ─────────────────────────────
export function Home() {
  const { me, fronts } = useField();
  const [lang, t] = useLang();
  const nav = useNavigate();
  const wf = fronts[0];
  const name = lang === "hi" ? me?.name_hi || me?.name : me?.name;
  return (
    <div className="space-y-4 p-4">
      <div>
        <div className="text-2xl font-bold">{t("hello")}, {name?.split(" ").slice(-1)[0] || ""} 👋</div>
        <div className="mt-1 text-base text-slate-600 dark:text-slate-300">
          {t("todayFront")}: <b>{wf ? `${wf.unit} · ${fronts.map((f) => f.name).join(" / ")}` : "…"}</b>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Tile icon={<Mic className="h-10 w-10" />} label={t("speak")} sub={t("speakHint")} className="bg-teal-700 text-white" onClick={() => nav("/field/chat?voice=1")} />
        <Tile icon={<Keyboard className="h-10 w-10" />} label={t("type")} className="bg-sky-700 text-white" onClick={() => nav("/field/chat?type=1")} />
        <Tile icon={<Camera className="h-10 w-10" />} label={t("photo")} className="bg-violet-700 text-white" onClick={() => nav("/field/photo")} />
        <Tile icon={<AlertOctagon className="h-10 w-10" />} label={t("problem")} className="bg-amber-500 text-slate-900" onClick={() => nav("/field/problem")} />
      </div>
      <button onClick={() => nav("/field/safety")} className="tap flex w-full items-center justify-center gap-3 rounded-2xl bg-red-600 py-4 text-xl font-bold text-white shadow-lg active:scale-[.99]">
        <ShieldAlert className="h-7 w-7" /> {t("safety")}
      </button>
      <button onClick={() => nav("/field/reports")} className="tap flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-slate-300 py-3 text-lg font-semibold dark:border-slate-700">
        <CheckCircle2 className="h-6 w-6" /> {t("myReports")}
      </button>
    </div>
  );
}

function Tile({ icon, label, sub, className, onClick }: any) {
  return (
    <button onClick={onClick} className={cn("flex aspect-square flex-col items-center justify-center gap-2 rounded-3xl p-3 text-center shadow-md active:scale-[.98]", className)}>
      {icon}
      <span className="text-lg font-bold leading-tight">{label}</span>
      {sub && <span className="text-xs opacity-80">{sub}</span>}
    </button>
  );
}

// ───────────────────────────── Chat (WhatsApp look) ─────────────────────────────
export function Chat() {
  const { thread, submit, answer } = useField();
  const [lang, t] = useLang();
  const loc = useLocation();
  const [text, setText] = useState("");
  const [showExtras, setShowExtras] = useState(false);
  const sp = useSpeech(lang);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [thread.length]);
  useEffect(() => { if (loc.search.includes("type")) inputRef.current?.focus(); }, []);

  const send = async (txt = text, extra: any = {}) => {
    if (!txt.trim() && !extra.extras) return;
    await submit({ text: txt.trim(), source_type: extra.source_type || "chat", ...extra });
    setText("");
    setShowExtras(true);
  };
  const stopAndSend = async () => {
    const said = await sp.stop();
    if (said) await send(said, { source_type: "voice", transcript_raw: said });
  };

  return (
    <div className="flex h-full min-h-[70dvh] flex-col bg-[#efeae2] dark:bg-slate-950">
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {thread.length === 0 && <div className="mx-auto mt-6 max-w-xs rounded-xl bg-white/80 p-3 text-center text-base text-slate-600">{t("typeHere")}</div>}
        {thread.map((b) => <ChatBubble key={b.id} b={b} onAnswer={answer} onFix={(s) => { setText(s); inputRef.current?.focus(); }} />)}
        {showExtras && <Extras onSend={(extras) => { send("", { extras }); setShowExtras(false); }} onClose={() => setShowExtras(false)} />}
        <div ref={endRef} />
      </div>
      {sp.listening && <div className="bg-teal-900 px-4 py-2 text-center text-base text-white">🎙️ {sp.interim || t("listening")}</div>}
      <div className="sticky bottom-0 flex items-center gap-2 bg-[#f0f2f5] p-2 dark:bg-slate-900">
        <input ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={t("typeHere")} className="tap min-w-0 flex-1 rounded-full bg-white px-4 text-lg outline-none dark:bg-slate-800" />
        {text.trim() ? (
          <button onClick={() => send()} className="tap flex w-14 items-center justify-center rounded-full bg-teal-700 text-white" aria-label={t("send")}><Send className="h-6 w-6" /></button>
        ) : (
          <button onPointerDown={() => sp.start()} onPointerUp={stopAndSend} onPointerLeave={() => sp.listening && stopAndSend()}
            className={cn("tap flex w-14 select-none items-center justify-center rounded-full text-white", sp.listening ? "bg-red-600" : "bg-teal-700")}
            aria-label={t("speak")} title={sp.supported ? t("speakHint") : t("noSpeech")}>
            <Mic className="h-6 w-6" />
          </button>
        )}
      </div>
      {!sp.supported && <div className="bg-amber-100 px-3 py-1 text-center text-xs text-amber-900">{t("noSpeech")}</div>}
    </div>
  );
}

function ChatBubble({ b, onAnswer, onFix }: { b: Bubble; onAnswer: (b: Bubble, v: string, l: string) => void; onFix: (s: string) => void }) {
  const [lang, t] = useLang();
  const mine = b.who === "me";
  const q = b.question;
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%] rounded-2xl px-3 py-2 text-base shadow-sm", mine ? "rounded-tr-sm bg-[#d9fdd3] text-slate-900" : "rounded-tl-sm bg-white text-slate-900")}>
        {b.photo && <img src={b.photo} className="mb-1 max-h-40 rounded-lg" alt="" />}
        <div className="whitespace-pre-wrap">{b.text}</div>
        {!mine && b.echoOf && !q && (
          <button onClick={() => onFix(b.echoOf!)} className="mt-1 inline-flex items-center gap-1 rounded-full border border-slate-300 px-3 py-1 text-sm"><Pencil className="h-3.5 w-3.5" /> {t("fix")}</button>
        )}
        {q && (
          <div className="mt-2 space-y-2">
            {q.options.map((o) => (
              <button key={o.value} disabled={!!b.answered} onClick={() => onAnswer(b, o.value, lang === "hi" ? o.label_hi || o.label : o.label)}
                className={cn("tap block w-full rounded-xl border-2 px-3 text-lg font-bold", b.answered === (lang === "hi" ? o.label_hi || o.label : o.label)
                  ? "border-teal-700 bg-teal-700 text-white" : "border-teal-700 text-teal-800 disabled:opacity-40")}>
                {lang === "hi" ? o.label_hi || o.label : o.label}
              </button>
            ))}
          </div>
        )}
        <div className="mt-1 text-right text-[11px] text-slate-500">
          {new Date(b.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          {mine && (b.status === "queued" ? " 📤" : " ✓✓")}
        </div>
      </div>
    </div>
  );
}

function Extras({ onSend, onClose }: { onSend: (x: any) => void; onClose: () => void }) {
  const [, t] = useLang();
  const [mp, setMp] = useState<Record<string, number>>({ fitter: 0, welder: 0, helper: 0, rigger: 0 });
  const [eq, setEq] = useState<string[]>([]);
  const [shift, setShift] = useState("day");
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-2xl bg-white p-3 shadow-sm dark:bg-slate-800">
      <button onClick={() => setOpen(!open)} className="tap flex w-full items-center justify-between text-left text-base font-semibold">
        <span className="flex items-center gap-2"><Users className="h-5 w-5" /> {t("extras")}</span><ChevronDown className={cn("h-5 w-5 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 pt-2">
          {Object.keys(mp).map((k) => (
            <div key={k} className="flex items-center justify-between">
              <span className="text-lg">{t(k as any)}</span>
              <div className="flex items-center gap-3">
                <button onClick={() => setMp({ ...mp, [k]: Math.max(0, mp[k] - 1) })} className="tap w-14 rounded-xl bg-slate-200 dark:bg-slate-700"><Minus className="mx-auto" /></button>
                <span className="w-8 text-center text-xl font-bold">{mp[k]}</span>
                <button onClick={() => setMp({ ...mp, [k]: mp[k] + 1 })} className="tap w-14 rounded-xl bg-slate-200 dark:bg-slate-700"><Plus className="mx-auto" /></button>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            {["crane", "hydra", "welding machine", "excavator"].map((x) => (
              <button key={x} onClick={() => setEq(eq.includes(x) ? eq.filter((y) => y !== x) : [...eq, x])}
                className={cn("tap rounded-xl border-2 px-3 text-base", eq.includes(x) ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300")}>
                <Truck className="mr-1 inline h-4 w-4" />{x}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {(["day", "night"] as const).map((s) => (
              <button key={s} onClick={() => setShift(s)} className={cn("tap flex-1 rounded-xl border-2 text-lg", shift === s ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300")}>
                {s === "day" ? `☀️ ${t("shiftDay")}` : `🌙 ${t("shiftNight")}`}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="tap flex-1 rounded-xl border-2 border-slate-300 text-lg">✕</button>
            <button onClick={() => onSend({ manpower: mp, equipment: eq, shift })} className="tap flex-[2] rounded-xl bg-teal-700 text-lg font-bold text-white"><Send className="mr-1 inline h-5 w-5" />{t("send")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────────────── Photo + note ─────────────────────────────
export function PhotoNote() {
  const { submit } = useField();
  const [, t] = useLang();
  const nav = useNavigate();
  const [file, setFile] = useState<{ name: string; blob: Blob } | null>(null);
  const [note, setNote] = useState("");
  const [samples, setSamples] = useState<string[]>([]);
  useEffect(() => { api("/api/samples").then((s) => setSamples(s.photos)).catch(() => {}); }, []);
  const pickSample = async (n: string) => { const b = await (await fetch(`/api/samples/${n}`)).blob(); setFile({ name: n, blob: b }); };
  const go = async () => {
    if (!file) return;
    await submit({ text: note, source_type: "photo" }, [file]);
    nav("/field/chat");
  };
  return (
    <div className="space-y-4 p-4">
      <label className="tap flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border-4 border-dashed border-violet-400 bg-violet-50 py-8 text-violet-900 dark:bg-violet-950 dark:text-violet-100">
        {file ? <img src={URL.createObjectURL(file.blob)} className="max-h-56 rounded-xl" alt="" /> : <><Camera className="h-12 w-12" /><span className="text-xl font-bold">{t("takePhoto")}</span></>}
        <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => e.target.files?.[0] && setFile({ name: e.target.files[0].name, blob: e.target.files[0] })} />
      </label>
      {samples.length > 0 && (
        <div className="text-xs text-slate-500">Demo photos (keep their EXIF):
          <div className="mt-1 flex flex-wrap gap-1">{samples.map((s) => <button key={s} onClick={() => pickSample(s)} className="rounded bg-slate-200 px-2 py-1 dark:bg-slate-700">{s}</button>)}</div>
        </div>
      )}
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("addNote")} className="tap w-full rounded-2xl border-2 border-slate-300 px-4 text-lg dark:bg-slate-800" />
      <button disabled={!file} onClick={go} className="tap flex w-full items-center justify-center gap-2 rounded-2xl bg-violet-700 py-3 text-xl font-bold text-white disabled:opacity-40">
        <Upload className="h-6 w-6" /> {t("send")}
      </button>
    </div>
  );
}

// ───────────────────────────── Work stopped / problem ─────────────────────────────
export function Problem() {
  const { submit } = useField();
  const [lang, t] = useLang();
  const nav = useNavigate();
  const [chip, setChip] = useState<string | null>(null);
  const chips = [
    { k: "rain", icon: <CloudRain />, cls: "bg-sky-600" }, { k: "material", icon: <Package />, cls: "bg-amber-600" },
    { k: "permit", icon: <FileWarning />, cls: "bg-orange-600" }, { k: "machine", icon: <Wrench />, cls: "bg-slate-600" },
    { k: "manpower", icon: <Users />, cls: "bg-indigo-600" }, { k: "drawing", icon: <HelpCircle />, cls: "bg-fuchsia-700" },
  ];
  const phrase = (k: string, since: string) => {
    const en: Record<string, string> = { rain: `Work stopped due to rain ${since}`, material: `Material not come, work stopped ${since}`, permit: `No permit, work stopped ${since}`,
      machine: `Machine breakdown, work stopped ${since}`, manpower: `Manpower short, work affected ${since}`, drawing: `Drawing issue, work on hold ${since}` };
    const hi: Record<string, string> = { rain: `Baarish ki wajah se ${since} kaam band`, material: `Material nahi aaya, ${since} kaam band`, permit: `Permit nahi hai, ${since} kaam band`,
      machine: `Machine kharab, ${since} kaam band`, manpower: `Log kam hain, manpower short ${since}`, drawing: `Drawing ki problem, ${since} kaam hold pe` };
    return (lang === "hi" ? hi : en)[k].replace(/\s+/g, " ").trim();
  };
  const times = lang === "hi" ? [["abhi se", "abhi se"], ["10 baje se", "10 baje se"], ["12 baje se", "12 baje se"], ["2 baje se", "2 baje se"], ["subah se", "subah se"]]
    : [["now", "from now"], ["10 am", "from 10am"], ["12 pm", "from 12pm"], ["2 pm", "from 2pm"], ["morning", "since morning"]];
  if (chip)
    return (
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2 text-xl font-bold"><Clock3 className="h-6 w-6" /> {t("since")}</div>
        {times.map(([label, val]) => (
          <button key={label} onClick={async () => { await submit({ text: phrase(chip, val), source_type: "chat" }); nav("/field/chat"); }}
            className="tap w-full rounded-2xl border-2 border-amber-500 text-xl font-bold">{label}</button>
        ))}
      </div>
    );
  return (
    <div className="grid grid-cols-2 gap-3 p-4">
      {chips.map((c) => (
        <button key={c.k} onClick={() => setChip(c.k)} className={cn("flex h-28 flex-col items-center justify-center gap-2 rounded-2xl text-lg font-bold text-white [&_svg]:h-8 [&_svg]:w-8", c.cls)}>
          {c.icon}{t(("chips_" + c.k) as any)}
        </button>
      ))}
      <button onClick={() => nav("/field/safety")} className="col-span-2 flex h-24 items-center justify-center gap-3 rounded-2xl bg-red-600 text-xl font-bold text-white">
        <ShieldAlert className="h-8 w-8" /> {t("chips_accident")}
      </button>
    </div>
  );
}

// ───────────────────────────── Safety report ─────────────────────────────
export function Safety() {
  const { submit } = useField();
  const [lang, t] = useLang();
  const [text, setText] = useState("");
  const [file, setFile] = useState<{ name: string; blob: Blob } | null>(null);
  const [done, setDone] = useState(false);
  const sp = useSpeech(lang);
  if (done)
    return (
      <div className="flex flex-col items-center gap-4 p-8 text-center">
        <ShieldAlert className="h-20 w-20 text-red-600" />
        <div className="text-2xl font-bold">{t("safetySent")}</div>
      </div>
    );
  return (
    <div className="space-y-4 p-4">
      <div className="rounded-2xl bg-red-50 p-3 text-lg font-semibold text-red-800 dark:bg-red-950 dark:text-red-100">{t("describeSafety")}</div>
      <textarea value={sp.listening ? sp.interim : text} onChange={(e) => setText(e.target.value)} rows={4}
        className="w-full rounded-2xl border-2 border-red-300 p-3 text-lg dark:bg-slate-800" />
      <div className="grid grid-cols-2 gap-3">
        <button onPointerDown={() => sp.start()} onPointerUp={async () => setText(await sp.stop())}
          className={cn("tap flex items-center justify-center gap-2 rounded-2xl text-lg font-bold text-white", sp.listening ? "bg-red-800" : "bg-slate-700")}>
          <Mic className="h-6 w-6" /> {t("speak")}
        </button>
        <label className="tap flex cursor-pointer items-center justify-center gap-2 rounded-2xl bg-slate-700 text-lg font-bold text-white">
          <Camera className="h-6 w-6" /> {file ? "✓" : t("photo")}
          <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => e.target.files?.[0] && setFile({ name: e.target.files[0].name, blob: e.target.files[0] })} />
        </label>
      </div>
      <button disabled={!text.trim()} onClick={async () => { await submit({ text, safety: true, source_type: "hse_form" }, file ? [file] : []); setDone(true); }}
        className="tap pulse-red flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 py-4 text-2xl font-bold text-white disabled:opacity-40">
        <ShieldAlert className="h-7 w-7" /> {t("send")}
      </button>
    </div>
  );
}

// ───────────────────────────── My reports ─────────────────────────────
export function MyReports() {
  const { userId, queued } = useField();
  const [, t] = useLang();
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    const load = () => api(`/api/field/my-reports?reporter_id=${userId}`).then(setRows).catch(() => {});
    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, [userId]);
  const icon: Record<string, [string, string]> = { recorded: ["✅", t("recorded")], checking: ["⏳", t("checking")], question: ["❓", t("question")], safety: ["🛑", t("safetyStatus")] };
  return (
    <div className="space-y-2 p-4">
      {queued.map((q) => (
        <div key={q.client_id} className="flex items-center gap-3 rounded-2xl bg-amber-50 p-3 dark:bg-amber-950">
          <span className="text-2xl">📤</span>
          <div className="min-w-0 flex-1"><div className="truncate text-base">{q.body.text || "📷"}</div><div className="text-sm text-amber-700">{t("waitingSignal")}</div></div>
        </div>
      ))}
      {rows.length === 0 && queued.length === 0 && <div className="py-10 text-center text-lg text-slate-500">{t("nothingToday")}</div>}
      {rows.map((r) => {
        const worst = r.events.find((e: any) => e.status === "safety") || r.events.find((e: any) => e.status === "question") || r.events.find((e: any) => e.status === "checking") || r.events[0];
        const [ic, label] = icon[worst?.status || "checking"];
        return (
          <div key={r.report_id} className="flex items-center gap-3 rounded-2xl bg-slate-50 p-3 dark:bg-slate-800">
            <span className="text-2xl">{ic}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-base">{r.text}</div>
              <div className="text-sm text-slate-500">{label} · {new Date(r.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
