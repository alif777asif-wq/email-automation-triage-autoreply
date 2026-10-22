"""Sender-role rule: a role address (billing@, orders@, notify@, hello@...) is not answered automatically.

People write to a support desk from a personal address (first.last@...). Role addresses are organisations, and organisations
that write to a support desk are overwhelmingly systems: receipts, renewals, status pages, password resets, surveys, chat
notifications. The wording guard (guard.py) cannot list every template, so this rule uses the shape of the sender address
instead. A role-address sender is sent to manual review: never auto-answered, never silently dropped.

The cost is real: a genuine message from a role mailbox (a business customer writing from accounts@) loses its automatic
acknowledgement and waits for a person. That is the safe side of the trade, and it is measured below, not assumed away.

Written after `data/formats-b` showed what the wording guard misses, so formats-a and formats-b are this rule's development
sets. `data/formats-c` was generated afterwards, with this file frozen (see data/RULES_FROZEN.sha256).
"""
from __future__ import annotations

import re

from .parse import Mail

ROLE_WORDS = frozenset("""
abuse accounting accounts admin administrator alert alerts billing bounce bounces care contact customer customers
delivery digest donotreply editor events feedback hello help helpdesk hi hostmaster info invoice invoices mail mailer
marketing news newsletter no-reply noreply notice notices notification notifications notify office order orders payment
payments postmaster press receipt receipts renewals reply reports sales security service services shipping status
subscriptions support survey system team tracking updates webmaster welcome
""".split())


def role_account(mail: Mail) -> bool:
    local = mail.sender.split("@")[0].lower()
    tokens = [t for t in re.split(r"[._+\-\d]+", local) if t]
    return local in ROLE_WORDS or bool(tokens) and tokens[0] in ROLE_WORDS
