import pytest

from mailtriage.extract import extract_fields
from conftest import HEAD, mail


def fields(subject, body, extra=""):
    return extract_fields(mail(HEAD + extra + f"Subject: {subject}\nContent-Type: text/plain\n\n{body}"))


@pytest.mark.parametrize("text", ["order ORD-48213", "order ORD48213", "order #48213", "order number 48213", "ORD 48213"])
def test_order_id_forms(text):
    assert fields("x", f"Please check {text}.")["order_id"] == "ORD-48213"


@pytest.mark.parametrize("text", ["INV-2026-0042", "INV 2026-0042", "INV2026-0042"])
def test_invoice_forms(text):
    assert fields("x", f"See {text}.")["invoice_no"] == "INV-2026-0042"


@pytest.mark.parametrize("text,expected", [("$1,249.00", "1249.00"), ("$89.50", "89.50"), ("USD 604.24", "604.24"),
                                           ("$12", "12.00")])
def test_amount_forms(text, expected):
    assert fields("x", f"Total {text} due.")["amount"] == expected


def test_subject_wins_over_body_and_missing_fields_are_absent():
    f = fields("Order ORD-11111 status", "My other order ORD-22222 is fine.")
    assert f["order_id"] == "ORD-11111" and "invoice_no" not in f and "amount" not in f


def test_bounced_address_from_delivery_status():
    m = mail("From: MAILER-DAEMON@mx.example.net\nTo: support@shop.example\nDate: Mon, 02 Mar 2026 09:00:00 +0000\nMessage-ID: <b@x>\n"
             "Content-Type: multipart/report; report-type=delivery-status; boundary=\"B\"\n\n--B\nContent-Type: text/plain\n\nx\n--B\n"
             "Content-Type: message/delivery-status\n\nReporting-MTA: dns; mx\n\nFinal-Recipient: rfc822; Gone@Example.org\n\n--B--\n")
    assert extract_fields(m)["bounced_address"] == "gone@example.org"
