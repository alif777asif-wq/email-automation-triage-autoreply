"""Field extraction: order id, invoice number, amount, bounced address."""
from __future__ import annotations

import re

from .parse import Mail

ORDER = [re.compile(r"\bORD[-\s]?(\d{5})\b", re.I), re.compile(r"\border\s*(?:number|no\.?|id)?\s*[:#]?\s*#?(\d{5})\b", re.I),
         re.compile(r"#(\d{5})\b")]
INVOICE = re.compile(r"\bINV[-\s]?(\d{4})-(\d{3,5})\b", re.I)
AMOUNT = re.compile(r"(?:\$|USD\s?)(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)", re.I)
FINAL_RCPT = re.compile(r"Final-Recipient:\s*rfc822;\s*(\S+@\S+)", re.I)
LEGACY_RCPT = re.compile(r"failed permanently:\s*\n\s*(\S+@\S+)", re.I)


def _first(rxs, texts):
    for text in texts:  # subject first, then body
        for rx in rxs:
            m = rx.search(text)
            if m:
                return m
    return None


def extract_fields(mail: Mail) -> dict:
    texts = [mail.subject, mail.body]
    out: dict = {}
    m = _first(ORDER, texts)
    if m:
        out["order_id"] = f"ORD-{m.group(1)}"
    m = _first([INVOICE], texts)
    if m:
        out["invoice_no"] = f"INV-{m.group(1)}-{int(m.group(2)):04d}"
    m = _first([AMOUNT], texts)
    if m:
        out["amount"] = f"{float(m.group(1).replace(',', '')):.2f}"
    m = FINAL_RCPT.search(mail.dsn_text) or LEGACY_RCPT.search(mail.body)
    if m:
        out["bounced_address"] = m.group(1).strip("<>;,").lower()
    return out
