"""Tiny in-process pub/sub for Server-Sent Events (live Gantt updates, HSE alerts).

The pipeline runs in sync code (threadpool); subscribers are asyncio queues. We hop
onto the event loop with call_soon_threadsafe.
"""
import asyncio
import json

_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None
muted = False            # the seed script mutes the bus


def bind_loop(loop):
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    return q


def unsubscribe(q):
    _subscribers.discard(q)


def publish(kind: str, data: dict):
    if muted or _loop is None:
        return
    msg = json.dumps({"kind": kind, "data": data}, default=str)

    def _put():
        for q in list(_subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    try:
        _loop.call_soon_threadsafe(_put)
    except RuntimeError:
        pass
