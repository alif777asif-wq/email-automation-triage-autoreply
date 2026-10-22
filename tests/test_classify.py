import pytest

from mailtriage.classify import classify
from mailtriage.datagen import OWN
from conftest import HEAD, mail


def decide(headers="", subject="Hello", body="hi", frm=None):
    raw = HEAD if frm is None else HEAD.replace("Ana Test <ana@example.com>", frm)
    return classify(mail(raw + headers + f"Subject: {subject}\nContent-Type: text/plain\n\n{body}"), OWN)


@pytest.mark.parametrize("headers,expected", [
    ("Auto-Submitted: auto-replied\n", "auto_reply"),
    ("Auto-Submitted: auto-generated\n", "auto_reply"),
    ("X-Autoreply: yes\n", "auto_reply"),
    ("Precedence: bulk\n", "bulk"),
    ("Precedence: junk\n", "bulk"),
    ("List-Unsubscribe: <mailto:u@example.net>\n", "bulk"),
    ("List-Id: <news.example.net>\n", "bulk"),
    ("Return-Path: <>\n", "bounce"),
])
def test_machine_headers_never_get_a_reply(headers, expected):
    d = decide(headers, subject="Where is my order ORD-12345? tracking", body="tracking please")
    assert d.category == expected and not d.reply_eligible


def test_auto_submitted_no_is_a_normal_human_message():
    d = decide("Auto-Submitted: no\n", subject="Question about invoice INV-2026-0001", body="Please check the invoice charge.")
    assert d.category == "billing" and d.reply_eligible


@pytest.mark.parametrize("frm", ["noreply@example.com", "No Reply <do-not-reply@example.com>", "MAILER-DAEMON@example.com"])
def test_noreply_and_daemon_senders_are_never_answered(frm):
    assert not decide(frm=frm, subject="Invoice", body="invoice").reply_eligible


def test_own_address_is_a_loop_guard():
    assert not decide(frm=f"Support <{OWN}>", subject="Invoice INV-2026-0001", body="invoice charge").reply_eligible


def test_out_of_office_without_any_header_is_still_caught():
    assert decide(subject="Out of Office: Order question", body="Thanks. I am out of the office until Monday.").category == "auto_reply"


@pytest.mark.parametrize("subject,body,cat", [
    ("Where is my order ORD-12345?", "Tracking has not updated.", "order_status"),
    ("Question about invoice INV-2026-0042", "The charge looks wrong.", "billing"),
    ("App keeps crashing", "Error after update.", "tech_support"),
    ("Pricing for 40 seats", "We would like a quote and a demo.", "sales_lead"),
    ("Refund for order ORD-12345", "Please refund me.", "refund_request"),
    ("Unsubscribe", "Remove me from your mailing list.", "unsubscribe"),
])
def test_intent_examples(subject, body, cat):
    assert decide(subject=subject, body=body).category == cat


def test_low_confidence_goes_to_manual_review_and_is_not_answered():
    d = decide(subject="Hello", body="Just saying hi, nothing specific.")
    assert d.category == "unknown" and d.queue == "manual_review" and not d.reply_eligible
