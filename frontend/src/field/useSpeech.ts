// Web Speech API (hi-IN / en-IN). The raw transcript is sent as transcript_raw — never discarded.
import { useRef, useState } from "react";

export function useSpeech(lang: "hi" | "en") {
  const Rec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const supported = !!Rec;
  const rec = useRef<any>(null);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const finalRef = useRef("");

  const start = () => {
    if (!supported || listening) return;
    const r = new Rec();
    r.lang = lang === "hi" ? "hi-IN" : "en-IN";
    r.interimResults = true;
    r.continuous = true;
    finalRef.current = "";
    r.onresult = (e: any) => {
      let fin = "", tmp = "";
      for (let i = 0; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) fin += t; else tmp += t;
      }
      finalRef.current = fin;
      setInterim(fin + tmp);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setInterim("");
    setListening(true);
    r.start();
  };

  const stop = (): Promise<string> =>
    new Promise((resolve) => {
      const r = rec.current;
      if (!r) return resolve(interim);
      r.onend = () => { setListening(false); resolve((finalRef.current || interim).trim()); };
      r.stop();
      setTimeout(() => resolve((finalRef.current || interim).trim()), 1200);
    });

  return { supported, listening, interim, start, stop };
}
