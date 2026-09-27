"""Optional real Telegram bot (set TELEGRAM_TOKEN). Long-polls the Bot API with httpx and
posts every message to the same ingest pipeline with channel="telegram".

Reporter mapping: a supervisor links their chat once with `/start R-KALITA`.
Clarifying questions come back as inline keyboard buttons (max one per report).
"""
import threading
import time

import httpx
from sqlmodel import select

from . import config
from .db import session_scope
from .models import Reporter
from .pipeline import ingest

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method, **params):
    return httpx.post(API.format(token=config.TELEGRAM_TOKEN, method=method), json=params, timeout=40).json()


def _reply(chat_id, text, question=None):
    kb = None
    if question:
        kb = {"inline_keyboard": [[{"text": o["label"], "callback_data": f"{question['event_id']}|{o['value']}"}] for o in question["options"]]}
    _call("sendMessage", chat_id=chat_id, text=text, **({"reply_markup": kb} if kb else {}))


def _handle(update):
    with session_scope() as s:
        if "callback_query" in update:
            cq = update["callback_query"]
            eid, val = cq["data"].split("|", 1)
            res = ingest.answer_clarification(s, int(eid), val)
            _reply(cq["message"]["chat"]["id"], res.get("reply", {}).get("en", "OK"))
            return
        msg = update.get("message") or {}
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text") or msg.get("caption") or ""
        if not chat_id or not text:
            return
        if text.startswith("/start"):
            rid = text.split(maxsplit=1)[1].strip() if " " in text else ""
            r = s.get(Reporter, rid)
            if r:
                r.telegram_chat_id = str(chat_id)
                s.add(r)
                s.commit()
                _reply(chat_id, f"Linked to {r.name}. Send your updates here.")
            else:
                _reply(chat_id, "Send /start <your reporter id>, e.g. /start R-KALITA")
            return
        r = s.exec(select(Reporter).where(Reporter.telegram_chat_id == str(chat_id))).first()
        loc = msg.get("location") or {}
        res = ingest.ingest(s, text=text, source_type="telegram", channel="telegram", reporter_id=r.id if r else None,
                            gps_lat=loc.get("latitude"), gps_lon=loc.get("longitude"), gps_accuracy=loc.get("horizontal_accuracy"))
        _reply(chat_id, res["reply"]["en"], res["reply"].get("question"))


def _loop():
    offset = 0
    while True:
        try:
            r = _call("getUpdates", offset=offset, timeout=30)
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                _handle(u)
        except Exception:
            time.sleep(5)


def start():
    threading.Thread(target=_loop, daemon=True, name="telegram-bot").start()
