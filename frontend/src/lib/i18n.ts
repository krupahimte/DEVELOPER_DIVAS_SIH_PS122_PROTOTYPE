// All Field App strings live here (Hindi / English). No jargon: never "activity ID" or "confidence".
import { useSyncExternalStore } from "react";

export type Lang = "en" | "hi";

const S = {
  hello: { en: "Namaste", hi: "नमस्ते" },
  todayFront: { en: "Today's work area", hi: "आज का काम" },
  online: { en: "Online", hi: "ऑनलाइन" },
  offlineWaiting: { en: "Offline: {n} reports waiting, will send automatically", hi: "ऑफ़लाइन: {n} रिपोर्ट रुकी हैं, सिग्नल आते ही अपने-आप जाएँगी" },
  sending: { en: "Sending {n}…", hi: "{n} भेज रहे हैं…" },
  speak: { en: "Speak update", hi: "बोलकर बताएं" },
  speakHint: { en: "Hold to talk", hi: "दबाकर रखें और बोलें" },
  type: { en: "Type update", hi: "लिखकर बताएं" },
  photo: { en: "Photo + note", hi: "फ़ोटो + नोट" },
  problem: { en: "Work stopped / Problem", hi: "काम रुका / समस्या" },
  safety: { en: "Safety report", hi: "सेफ्टी रिपोर्ट" },
  myReports: { en: "My reports", hi: "मेरी रिपोर्ट" },
  send: { en: "Send", hi: "भेजें" },
  typeHere: { en: "What was done today?", hi: "आज क्या काम हुआ?" },
  listening: { en: "Listening… release to send", hi: "सुन रहे हैं… छोड़ें और भेजें" },
  noSpeech: { en: "Voice not supported on this phone — please type", hi: "इस फ़ोन पर आवाज़ नहीं — कृपया लिखें" },
  chips_rain: { en: "Rain", hi: "बारिश" },
  chips_material: { en: "Material not come", hi: "मटेरियल नहीं आया" },
  chips_permit: { en: "No permit", hi: "परमिट नहीं" },
  chips_machine: { en: "Machine broke", hi: "मशीन खराब" },
  chips_manpower: { en: "Manpower short", hi: "लोग कम" },
  chips_drawing: { en: "Drawing issue", hi: "ड्रॉइंग समस्या" },
  chips_accident: { en: "Accident / near-miss", hi: "दुर्घटना / बाल-बाल बचे" },
  since: { en: "Since what time?", hi: "कब से?" },
  safetySent: { en: "Sent to HSE officer. Someone will call you.", hi: "सेफ्टी अधिकारी को भेजा। कोई आपको कॉल करेगा।" },
  describeSafety: { en: "What happened? (speak or type)", hi: "क्या हुआ? (बोलें या लिखें)" },
  extras: { en: "Add people & machines (optional)", hi: "लोग और मशीन जोड़ें (वैकल्पिक)" },
  shiftDay: { en: "Day", hi: "दिन" },
  shiftNight: { en: "Night", hi: "रात" },
  recorded: { en: "Recorded", hi: "दर्ज" },
  checking: { en: "Checking", hi: "जाँच में" },
  question: { en: "Question for you", hi: "आपसे सवाल" },
  waitingSignal: { en: "Waiting for signal", hi: "सिग्नल का इंतज़ार" },
  safetyStatus: { en: "With safety officer", hi: "सेफ्टी अधिकारी के पास" },
  fix: { en: "Fix", hi: "सुधारें" },
  back: { en: "Back", hi: "वापस" },
  takePhoto: { en: "Take / choose photo", hi: "फ़ोटो लें / चुनें" },
  addNote: { en: "Add a short note", hi: "छोटा नोट लिखें" },
  nothingToday: { en: "No reports yet today", hi: "आज अभी कोई रिपोर्ट नहीं" },
  fitter: { en: "Fitter", hi: "फिटर" }, welder: { en: "Welder", hi: "वेल्डर" }, helper: { en: "Helper", hi: "हेल्पर" }, rigger: { en: "Rigger", hi: "रिगर" },
};

export type Key = keyof typeof S;

let lang: Lang = (localStorage.getItem("lang") as Lang) || "hi";
const subs = new Set<() => void>();
export function setLang(l: Lang) {
  lang = l;
  localStorage.setItem("lang", l);
  subs.forEach((f) => f());
}
export function useLang(): [Lang, (k: Key, vars?: Record<string, string | number>) => string] {
  const l = useSyncExternalStore((cb) => (subs.add(cb), () => subs.delete(cb)), () => lang);
  const t = (k: Key, vars?: Record<string, string | number>) => {
    let s = S[k]?.[l] ?? String(k);
    for (const [a, b] of Object.entries(vars || {})) s = s.replace(`{${a}}`, String(b));
    return s;
  };
  return [l, t];
}
