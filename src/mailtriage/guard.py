"""Second look at mail the intent rules would answer: does it read like automated mail?

classify.py recognises machine mail by its standard markers (Auto-Submitted, Precedence, List-*, DSN structure, no-reply
senders). Real automated mail often carries none of them: a gateway stripped the headers, or a transactional sender
(receipts, shipping notices, sign-in codes, leave notices) never added them. Without a marker, the intent rules read
"Your receipt from Acme" as a billing question and "Your order has shipped" as an order enquiry.

This module scores the wording of the message and the role of the sender. It can only REMOVE an automatic reply, never add
one: a message that scores at or above THRESHOLD goes to manual review (never auto-answered, never silently dropped), so a
false positive costs a person a glance, not a customer an answer.

Written after `data/formats-a` (the first machine-mail format set) showed unmarked mail being answered; that set is this
module's development set. `data/formats-b` was generated afterwards, with this file frozen (see data/RULES_FROZEN.sha256).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import Mail

I = re.I | re.S
THRESHOLD = 3

# Strong (3): wording people do not send to a support desk, but machines do.
STRONG = {
    "leave notice": re.compile(
        r"\b(when|once|after) (i|we) (return|get back|am back|are back)\b|"
        r"\b(i am|i'm|we are|we're|i will be|i'll be) (currently |now )?(away|out of (the )?(office|country)|"
        r"on (annual |sick |maternity |paternity )?(leave|vacation|holiday)|travell?ing)\b.{0,100}?\b(until|through|returning|back|return)\b", I),
    "limited email access": re.compile(r"\blimited (access to|email access)\b|\bcheck(ing)? (my )?(e-?mail|messages) (only )?(occasionally|intermittently)\b", I),
    "automatic confirmation": re.compile(r"\bautomatic(ally)?[- ](confirmation|reply|response|acknowledg(e)?ment|notification)\b|\bauto-?(reply|responder|generated)\b", I),
    "no-reply notice": re.compile(r"\bdo not reply (directly )?to this (e-?mail|message)\b|\bplease do not reply\b|\b(mailbox|address|inbox) is not monitored\b|\bunmonitored\b", I),
}
# Medium (2): transactional templates.
MEDIUM = {
    "receipt wording": re.compile(r"\b(receipt|invoice|statement) (from|for|number)\b|\bamount paid\b|\bpayment (received|successful|confirmation)\b|\bpayment method:|\bcard ending\b|\bthank you for your payment\b", I),
    "shipping wording": re.compile(r"\b(has|have) (shipped|been (shipped|dispatched|despatched|delivered))\b|\btracking number\b|\bestimated delivery\b|\bon its way\b|\bout for delivery\b", I),
    "sign-in or code wording": re.compile(r"\b(sign[- ]?in|log[- ]?in|verification|security|one[- ]time|authentication) (code|link)\b|\bexpires in \d+ (minutes|hours)\b|\bif you (didn'?t|did not) (request|make|create|initiate)\b|\bsafely ignore this (e-?mail|message)\b", I),
    # an unsubscribe or preferences LINE or footer, not a customer saying they might unsubscribe
    "notification wording": re.compile(r"\b(commented on|mentioned you|assigned you|invited you|shared .{0,40}? with you)\b|\bview (it )?(online|in (your )?browser)\b|"
                                       r"(^|\n)\s*(unsubscribe|manage (your )?(e-?mail )?(preferences|notifications))\b|\bclick (here )?to unsubscribe\b|\bunsubscribe (here|link)\b", I),
}
# Weak (1): the sender's role.
ROLE_SENDER = re.compile(r"^(receipts?|invoices?|statements?|payments?|orders?|shipping|delivery|tracking|security|alerts?|accounts?|notify|system|automated|updates?|digest|mailer)\b", I)


@dataclass(frozen=True)
class Verdict:
    automated: bool
    score: int
    cues: tuple[str, ...]


def looks_automated(mail: Mail) -> Verdict:
    text = f"{mail.subject}\n{mail.body}"
    score, cues = 0, []
    for name, rx in STRONG.items():
        if rx.search(text):
            score, cues = score + 3, cues + [name]
    for name, rx in MEDIUM.items():
        if rx.search(text):
            score, cues = score + 2, cues + [name]
    local = mail.sender.split("@")[0]
    if ROLE_SENDER.match(local):
        score, cues = score + 1, cues + ["role-account sender"]
    return Verdict(score >= THRESHOLD, score, tuple(cues))
