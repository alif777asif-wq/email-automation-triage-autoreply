"""Baseline for comparison: the auto-responder most quick scripts implement.

It answers every message that is not from its own address, then records progress in a cursor file.
No machine-mail guards, no Message-ID de-duplication, no cooldown, no outbox: if it is killed after the
send but before the cursor write, the message is answered again after the restart.
"""
from __future__ import annotations

import logging
import os
import smtplib
import uuid
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

from .datagen import OWN
from .faults import crashpoint, send_delay

log = logging.getLogger("mailtriage.naive")


def run_naive(inbox: Path, cursor: Path, host: str, port: int, own_address: str = OWN) -> dict:
    done = set(cursor.read_text().split()) if cursor.exists() else set()
    sent = 0
    conn = smtplib.SMTP(host, port, timeout=15)
    for path in sorted(inbox.glob("*.eml")):
        if path.name in done:
            continue
        msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes(), headersonly=True)
        sender = parseaddr(str(msg["From"] or ""))[1]
        if sender and sender.lower() != own_address.lower():
            reply = EmailMessage()
            reply["From"], reply["To"] = own_address, sender
            reply["Subject"] = "Re: " + str(msg["Subject"] or "")
            reply["Message-ID"] = f"<{uuid.uuid4().hex}@naive.example>"
            reply["In-Reply-To"] = str(msg["Message-ID"] or "")
            reply.set_content("Thanks for your email. We will get back to you soon.\n")
            crashpoint("before_smtp")
            send_delay()
            conn.send_message(reply)
            crashpoint("after_smtp_before_commit")
            sent += 1
        with open(cursor, "a", encoding="utf-8") as fh:
            fh.write(path.name + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        crashpoint("after_sent_commit")
    conn.quit()
    return {"sent": sent}
