"""Devanagari → Roman (Hinglish) normalisation for hi-IN voice transcripts.

Chrome's hi-IN recogniser writes English site words in Devanagari
("रैक बी पे स्पूल 3 और 4 इरेक्ट हो गए"). The extractor works on Roman text, so we
normalise with a site-word dictionary first and a plain character transliteration
as fallback. The original transcript is kept verbatim as `transcript_raw`.
"""
import re

WORDS = {
    "रैक": "rack", "रेक": "rack", "बी": "B", "सी": "C", "ए": "A", "डी": "D", "पे": "pe", "पर": "par", "में": "mein", "मे": "mein",
    "स्पूल": "spool", "स्पूल्स": "spools", "इरेक्ट": "erect", "इरेक्शन": "erection", "हो": "ho", "गए": "gaye", "गये": "gaye", "गया": "gaya",
    "गई": "gayi", "गयी": "gayi", "और": "aur", "फिटर": "fitter", "फ़िटर": "fitter", "वेल्डर": "welder", "हेल्पर": "helper", "रिगर": "rigger",
    "थे": "the", "था": "tha", "है": "hai", "हैं": "hain", "लाइन": "line", "हाइड्रोटेस्ट": "hydrotest", "हाइड्रो": "hydro", "टेस्ट": "test",
    "कंप्लीट": "complete", "कम्पलीट": "complete", "पूरा": "pura", "पूरी": "poori", "वेल्डिंग": "welding", "स्टार्ट": "start", "शुरू": "shuru",
    "बारिश": "baarish", "बरसात": "barsaat", "काम": "kaam", "बंद": "band", "रुक": "ruk", "मटेरियल": "material", "नहीं": "nahi", "आया": "aaya",
    "परमिट": "permit", "क्रेन": "crane", "खराब": "kharab", "मशीन": "machine", "नियर": "near", "मिस": "miss", "स्लिंग": "sling",
    "स्लिप": "slip", "फिसल": "slipped", "गिरा": "gira", "एक्सकेवेशन": "excavation", "खुदाई": "khudai", "केबल": "cable", "पुलिंग": "pulling",
    "ट्रे": "tray", "यूनिट": "unit", "टैंक": "tank", "फार्म": "farm", "पंप": "pump", "हाउस": "house", "आज": "aaj", "कल": "kal",
    "बजे": "baje", "से": "se", "तक": "tak", "लोग": "log", "मजदूर": "mazdoor", "कंक्रीट": "concrete", "डाला": "dala", "ढलाई": "dhalai",
    "रात": "raat", "दिन": "din", "शिफ्ट": "shift", "जॉइंट": "joint", "जोड़": "jod", "किया": "kiya", "कर": "kar", "दिया": "diya",
    "चालू": "chalu", "जारी": "jari", "नाली": "nali", "ड्रेनेज": "drainage", "टेंपरेरी": "temporary", "गेट": "gate", "के": "ke", "का": "ka",
    "की": "ki", "पास": "paas", "स्पूल्स": "spools", "नंबर": "number", "ड्राइंग": "drawing", "मैनपावर": "manpower", "कम": "kam",
}
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# minimal phonetic fallback
_V = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n", "ः": "h", "ृ": "ri", "्": ""}
_C = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
      "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l",
      "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ज़": "z", "फ़": "f", "ड़": "r", "ढ़": "rh"}
_IV = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o"}

_DEV = re.compile(r"[ऀ-ॿ]")


def has_devanagari(text: str) -> bool:
    return bool(_DEV.search(text or ""))


def _char_translit(word: str) -> str:
    out = []
    for i, ch in enumerate(word):
        if ch in _C:
            out.append(_C[ch])
            nxt = word[i + 1] if i + 1 < len(word) else ""
            if nxt not in _V and nxt != "":
                out.append("a")
        elif ch in _V:
            out.append(_V[ch])
        elif ch in _IV:
            out.append(_IV[ch])
        else:
            out.append(ch)
    return "".join(out)


def normalise(text: str) -> str:
    text = text.translate(_DIGITS).replace("।", ".")
    if not has_devanagari(text):
        return text

    def repl(m):
        w = m.group(0)
        return WORDS.get(w, _char_translit(w))

    return re.sub(r"[ऀ-ॿ]+", repl, text)
