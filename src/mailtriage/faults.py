"""Deterministic crash injection for the crash-recovery tests.

MAILTRIAGE_CRASH="<point>:<n>"  -> SIGKILL this process at the n-th time <point> is reached.
MAILTRIAGE_SEND_DELAY_MS        -> sleep before each SMTP send (widens the window for random kills).
Both are inert unless the environment variables are set.
"""
from __future__ import annotations

import os
import signal
import time

POINTS = ["after_ingest_row", "after_triage_row", "before_smtp", "after_smtp_before_commit", "after_sent_commit"]
_counts: dict[str, int] = {}


def crashpoint(name: str) -> None:
    spec = os.environ.get("MAILTRIAGE_CRASH")
    if not spec:
        return
    point, n = spec.split(":")
    if point != name:
        return
    _counts[name] = _counts.get(name, 0) + 1
    if _counts[name] == int(n):
        os.kill(os.getpid(), signal.SIGKILL)


def send_delay() -> None:
    ms = float(os.environ.get("MAILTRIAGE_SEND_DELAY_MS", "0") or 0)
    if ms:
        time.sleep(ms / 1000)
