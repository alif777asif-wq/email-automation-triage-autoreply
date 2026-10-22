"""Ingest -> triage -> send. Every stage is idempotent, so the whole run can be killed and restarted at any point."""
from __future__ import annotations

import csv
import json
import logging
import time
from collections import Counter
from pathlib import Path

from .classify import Decision, classify
from .datagen import OWN
from .extract import extract_fields
from .faults import crashpoint
from .guard import looks_automated
from .parse import Mail, parse_file
from .roles import role_account
from .sender import reply_id_for, send_pending, ticket_for
from .smtp_sink import Ledger
from .store import Store

log = logging.getLogger("mailtriage")
COOLDOWN_HOURS = 24


def ingest(store: Store, inbox: Path) -> Counter:
    stats: Counter = Counter()
    for path in sorted(inbox.glob("*.eml")):
        if store.has_file(path.name):
            continue
        fresh = store.add_received(parse_file(path))
        stats["new" if fresh else "redelivered"] += 1
        crashpoint("after_ingest_row")
    return stats


GUARD_LEVELS = ("off", "wording", "full")


def triage(store: Store, own_address: str, guard: str = "full") -> Counter:
    """guard: "off" = standard markers only; "wording" adds guard.py; "full" adds the sender-role rule (roles.py)."""
    stats: Counter = Counter()
    for row in store.rows("RECEIVED"):
        mail = Mail.from_dict(json.loads(row["parsed"]))
        d: Decision = classify(mail, own_address)
        if guard != "off" and d.reply_eligible:  # a second look: would this message be answered although it reads as automated?
            verdict = looks_automated(mail)
            cues = list(verdict.cues) if verdict.automated else []
            if guard == "full" and role_account(mail):
                cues.append("role-account sender")
            if cues:
                d = Decision("unknown", "manual_review", False, f"reads as automated mail ({', '.join(cues)}) -> manual review",
                             d.score, d.margin)
                stats["guard_held_for_review"] += 1
        fields = extract_fields(mail)
        suppress: list[tuple[str, str]] = []
        state, reason = "DONE", d.reason
        if d.category == "unsubscribe":
            suppress.append((mail.sender, "unsubscribe"))
            reason = "unsubscribe request -> added to suppression list, no reply"
        elif d.category == "bounce" and "bounced_address" in fields:
            suppress.append((fields["bounced_address"], "bounce"))
            reason = "bounce -> recipient added to suppression list, no reply"
        elif d.reply_eligible:
            if store.is_suppressed(mail.sender):
                reason = "sender is on the suppression list"
            elif store.recent_reply(mail.sender, mail.sent_at, COOLDOWN_HOURS):
                reason = f"already acknowledged within {COOLDOWN_HOURS}h (cooldown)"
            else:
                state, reason = "QUEUED", "auto-acknowledgement queued"
        store.finish_triage(mail.message_id, state, d, fields, ticket_for(mail.message_id),
                            reply_id_for(mail.message_id), reason, suppress)
        stats[state] += 1
        crashpoint("after_triage_row")
    return stats


def export_csv(store: Store, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "message_id", "sender", "sent_at_utc", "category", "queue", "state", "ticket", "fields", "reason"])
        for r in store.all_rows():
            w.writerow([r["file"], r["message_id"], r["sender"], r["sent_at"], r["category"], r["queue"], r["state"],
                        r["ticket"], r["fields"], r["reason"]])


def run_pipeline(inbox: Path, db: Path, smtp: tuple[str, int], sink_dir: Path, own_address: str = OWN,
                 guard: str = "full") -> dict:
    store = Store(db)
    t0 = time.perf_counter()
    ing = ingest(store, inbox)
    t1 = time.perf_counter()
    tri = triage(store, own_address, guard)
    t2 = time.perf_counter()
    snd = send_pending(store, Ledger(sink_dir), smtp[0], smtp[1], own_address)
    t3 = time.perf_counter()
    counts = store.counts()
    store.close()
    result = {"ingest": dict(ing), "triage": dict(tri), "send": dict(snd), "states": counts,
              "seconds": {"ingest_parse": round(t1 - t0, 3), "triage": round(t2 - t1, 3), "send": round(t3 - t2, 3)}}
    log.info("run complete: %s", json.dumps(result))
    return result
