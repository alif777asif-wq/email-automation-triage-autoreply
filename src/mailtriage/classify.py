"""Rule-based triage: hard machine-mail guards first, then weighted intent keywords.

Anything below the confidence threshold goes to manual review and is NEVER auto-answered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import Mail

REPLY_CATEGORIES = {"billing", "order_status", "tech_support", "sales_lead", "refund_request"}
QUEUES = {"billing": "billing", "refund_request": "billing", "order_status": "fulfilment", "tech_support": "support",
          "sales_lead": "sales", "unsubscribe": "suppression", "bounce": "suppression", "auto_reply": "none",
          "bulk": "none", "unknown": "manual_review"}

I = re.I
INTENTS = {
    "billing": [(r"\binvoices?\b", 3), (r"\bbilling\b", 3), (r"\bcharge[sd]?\b", 2), (r"\bpayments?\b", 2),
                (r"\breceipt\b", 2), (r"\bVAT\b", 2), (r"\baccounting\b", 1), (r"\bINV[-\s]?\d{4}", 2)],
    "order_status": [(r"\border\b", 1.5), (r"\bORD[-\s]?\d{5}\b|#\d{5}\b", 1), (r"\btracking\b", 3),
                     (r"\b(ship(ped|ping|ment)?|deliver(y|ed)?|package|parcel)\b", 2), (r"\bwhere is\b", 2),
                     (r"\b(arrive|arrived|arrival)\b", 1.5)],
    "tech_support": [(r"\b(crash(es|ed|ing)?|bug|glitch)\b", 3), (r"\berrors?\b", 2.5),
                     (r"\b(sign|log) ?in\b|\bpassword\b", 2.5), (r"\b(not|stopped|n't) working\b|\bdoes ?n[o']t work\b", 3),
                     (r"\b(app|dashboard|browser|version|update|sync|export(ing)?)\b", 1), (r"\bblank page\b", 2)],
    "sales_lead": [(r"\b(pricing|prices?|quote)\b", 3), (r"\bdemo\b", 3), (r"\benterprise\b", 2.5),
                   (r"\b(seats|licen[cs]es)\b", 2), (r"\b(reseller|partnership|partner)\b", 3),
                   (r"\bvolume discounts?\b", 2), (r"\bevaluating\b", 2), (r"\bannual contracts?\b", 2)],
    "refund_request": [(r"\brefund(s|ed)?\b", 4), (r"\breturn(ing|ed)?\b", 2.5), (r"\bmoney back\b", 4),
                       (r"\bcancel\b", 2.5), (r"\bdamaged\b", 1.5)],
    "unsubscribe": [(r"\bunsubscribe\b", 5), (r"\bremove me\b", 5), (r"\bstop (emailing|sending|messaging)\b", 5),
                    (r"\bmailing list\b", 3), (r"\bno longer want to receive\b", 4), (r"\bopt(ing)? out\b", 4),
                    (r"^\s*stop\s*$", 5)],
}
COMPILED = {c: [(re.compile(p, I | re.M), w) for p, w in rules] for c, rules in INTENTS.items()}

DSN_CUES = re.compile(r"undelivered mail returned|delivery status notification|delivery to the following recipient "
                      r"(has )?failed|message (could not be|couldn't be) delivered", I)
AUTO_SUBJECT = re.compile(r"^\s*(automatic reply|auto(matic)?[- ]?reply|out of (the )?office)\b", I)
AUTO_BODY = re.compile(r"\bout of the office\b|\bthis is an automated (message|reply)\b|\bautomatic(ally)? generated\b", I)
BULK_BODY = re.compile(r"view this email in your browser|you are receiving this email because", I)

MIN_SCORE = 3.0
MIN_MARGIN = 1.5


@dataclass
class Decision:
    category: str
    queue: str
    reply_eligible: bool
    reason: str
    score: float = 0.0
    margin: float = 0.0


def machine_category(mail: Mail) -> tuple[str, str] | None:
    f = mail.flags
    text = f"{mail.subject}\n{mail.body}"
    if f["is_dsn"] or f["null_return_path"] or DSN_CUES.search(text):
        return "bounce", "delivery-status notification"
    if f["auto_submitted"] or f["x_autoreply"] or f["precedence"] == "auto_reply" or AUTO_SUBJECT.search(mail.subject) \
            or AUTO_BODY.search(mail.body):
        return "auto_reply", "auto-reply markers (RFC 3834 / subject / body)"
    if f["list_headers"] or f["precedence"] in ("bulk", "junk", "list") or f["noreply_sender"] or BULK_BODY.search(mail.body):
        return "bulk", "bulk / no-reply sender markers"
    return None


def intent_scores(mail: Mail) -> dict[str, float]:
    scores = {}
    for cat, rules in COMPILED.items():
        s = 0.0
        for rx, w in rules:
            if rx.search(mail.subject):
                s += 2 * w
            n = len(rx.findall(mail.body))
            if n:
                s += w * (1 if n == 1 else 1.5)
        scores[cat] = s
    return scores


def classify(mail: Mail, own_address: str) -> Decision:
    if mail.sender == own_address.lower():
        return Decision("auto_reply", QUEUES["auto_reply"], False, "sent by our own address (loop guard)")
    guard = machine_category(mail)
    if guard:
        cat, why = guard
        return Decision(cat, QUEUES[cat], False, why)
    scores = intent_scores(mail)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (best, s1), (_, s2) = ranked[0], ranked[1]
    if s1 < MIN_SCORE or (s1 - s2) < MIN_MARGIN:
        return Decision("unknown", QUEUES["unknown"], False, "low confidence -> manual review", s1, s1 - s2)
    return Decision(best, QUEUES[best], best in REPLY_CATEGORIES, f"intent keywords ({best})", s1, s1 - s2)
