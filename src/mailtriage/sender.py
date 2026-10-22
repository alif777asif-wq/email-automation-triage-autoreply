"""Reply construction and crash-safe sending."""
from __future__ import annotations

import hashlib
import json
import logging
import smtplib
import time
from collections import Counter
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

from .faults import crashpoint, send_delay
from .smtp_sink import Ledger
from .store import Store

log = logging.getLogger("mailtriage")
TEAM = {"billing": "billing", "refund_request": "billing", "order_status": "fulfilment", "tech_support": "support",
        "sales_lead": "sales"}
TOPIC = {"billing": "your billing question", "refund_request": "your refund request", "order_status": "your order question",
         "tech_support": "the problem you reported", "sales_lead": "your enquiry"}
MAX_ATTEMPTS = 3


def ticket_for(message_id: str) -> str:
    return "TKT-" + hashlib.sha1(message_id.encode()).hexdigest()[:8].upper()


def reply_id_for(message_id: str) -> str:
    return f"<reply.{hashlib.sha1(message_id.encode()).hexdigest()[:20]}@triage.example>"


def build_reply(row, own_address: str) -> EmailMessage:
    fields = json.loads(row["fields"] or "{}")
    first = (row["sender_name"] or "").split(" ")[0] or "there"
    ref = f"\nReference: order {fields['order_id']}." if "order_id" in fields else (
        f"\nReference: invoice {fields['invoice_no']}." if "invoice_no" in fields else "")
    cat = row["category"]
    msg = EmailMessage()
    msg["From"] = own_address
    msg["To"] = row["sender"]
    msg["Subject"] = "Re: " + (row["subject"] or "your message")
    msg["Message-ID"] = row["reply_id"]  # deterministic: the same inbound message always yields the same id
    msg["In-Reply-To"] = row["message_id"]
    msg["References"] = row["message_id"]
    msg["Date"] = format_datetime(datetime.now(timezone.utc))
    msg["Auto-Submitted"] = "auto-replied"  # RFC 3834: other auto-responders must not answer this
    msg["Precedence"] = "auto_reply"
    msg["X-Auto-Response-Suppress"] = "All"
    msg.set_content(
        f"Hello {first},\n\nThanks for getting in touch. We have received {TOPIC[cat]} and logged it as ticket "
        f"{row['ticket']}.{ref}\n\nA member of our {TEAM[cat]} team will follow up by email.\n\n"
        "This is an automatic acknowledgement.\n")
    return msg


def reconcile(store: Store, ledger: Ledger, row, stats: Counter) -> None:
    """Decide what really happened to a message left in SENDING by a crash or an ambiguous SMTP error."""
    mid = row["message_id"]
    if not ledger.available():
        store.transition(mid, "REVIEW", "SENDING")
        stats["review"] += 1
        log.warning("RECONCILE %s -> REVIEW (ledger unavailable)", mid)
    elif ledger.contains(row["reply_id"]):
        store.transition(mid, "SENT", "SENDING")
        stats["reconciled_sent"] += 1
        log.info("RECONCILE %s -> SENT (already delivered; not re-sent)", mid)
    elif row["attempts"] >= MAX_ATTEMPTS:
        store.transition(mid, "REVIEW", "SENDING")
        stats["review"] += 1
        log.warning("RECONCILE %s -> REVIEW (max attempts)", mid)
    else:
        store.transition(mid, "QUEUED", "SENDING")
        stats["requeued"] += 1
        log.info("RECONCILE %s -> QUEUED (never delivered; will send)", mid)


def send_pending(store: Store, ledger: Ledger, host: str, port: int, own_address: str) -> Counter:
    stats: Counter = Counter()
    for row in store.rows("SENDING"):  # left over from a previous, interrupted run
        reconcile(store, ledger, row, stats)
    conn = None
    for row in store.rows("QUEUED"):
        mid = row["message_id"]
        if conn is None:
            try:
                conn = smtplib.SMTP(host, port, timeout=15)
            except (OSError, smtplib.SMTPException) as exc:
                # Could not even connect: nothing was sent, so this is NOT ambiguous. Leave everything QUEUED for the next run.
                stats["deferred_server_unreachable"] = len(store.rows("QUEUED"))
                log.warning("SMTP server unreachable (%s); %d replies stay queued", exc, stats["deferred_server_unreachable"])
                break
        store.transition(mid, "SENDING", "QUEUED", bump_attempts=True)  # committed BEFORE the network call
        crashpoint("before_smtp")
        send_delay()
        try:
            conn.send_message(build_reply(row, own_address), from_addr="", to_addrs=[row["sender"]])  # MAIL FROM:<>
        except smtplib.SMTPResponseException as exc:
            conn = None
            if exc.smtp_code >= 500:
                store.transition(mid, "FAILED", "SENDING")
                stats["failed"] += 1
                log.warning("permanent SMTP failure for %s: %s", mid, exc.smtp_code)
                continue
            reconcile(store, ledger, store.db.execute("SELECT * FROM mail WHERE message_id=?", (mid,)).fetchone(), stats)
            continue
        except (smtplib.SMTPException, OSError) as exc:
            conn = None
            log.warning("ambiguous SMTP outcome for %s (%s); reconciling", mid, exc)
            reconcile(store, ledger, store.db.execute("SELECT * FROM mail WHERE message_id=?", (mid,)).fetchone(), stats)
            continue
        crashpoint("after_smtp_before_commit")
        store.transition(mid, "SENT", "SENDING")
        stats["sent"] += 1
        crashpoint("after_sent_commit")
    if conn:
        try:
            conn.quit()
        except smtplib.SMTPException:
            pass
    return stats
