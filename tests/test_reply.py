import json

from mailtriage.classify import classify
from mailtriage.datagen import OWN
from mailtriage.parse import parse_bytes
from mailtriage.sender import build_reply, reply_id_for, ticket_for


def row(**kw):
    base = dict(message_id="<abc@example.com>", sender="ana@example.com", sender_name="Ana Test", subject="Where is ORD-12345?",
                category="order_status", fields=json.dumps({"order_id": "ORD-12345"}), ticket=ticket_for("<abc@example.com>"),
                reply_id=reply_id_for("<abc@example.com>"))
    base.update(kw)
    return base


def test_reply_headers_follow_rfc3834_and_threading():
    m = build_reply(row(), OWN)
    assert m["Auto-Submitted"] == "auto-replied" and m["In-Reply-To"] == "<abc@example.com>"
    assert m["Message-ID"] == reply_id_for("<abc@example.com>")
    assert "ORD-12345" in m.get_content() and m["To"] == "ana@example.com"


def test_reply_ids_are_deterministic_and_unique_per_message():
    assert reply_id_for("<a@x>") == reply_id_for("<a@x>") != reply_id_for("<b@x>")
    assert ticket_for("<a@x>") == ticket_for("<a@x>")


def test_our_own_reply_would_be_ignored_by_an_identical_pipeline_on_the_other_side():
    """The loop closes: classifying our reply (as the remote side would) yields a machine category and no auto-answer."""
    remote = parse_bytes(build_reply(row(), OWN).as_bytes())
    d = classify(remote, "someone-else@example.com")
    assert d.category == "auto_reply" and not d.reply_eligible
