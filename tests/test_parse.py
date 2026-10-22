from mailtriage.parse import parse_bytes
from conftest import HEAD, mail


def test_quoted_history_and_signature_are_removed():
    m = mail(HEAD + "Subject: Hi\nContent-Type: text/plain\n\nPlease check invoice INV-2026-0042.\n\n"
             "On Mon, 2 Mar 2026, Support <support@shop.example> wrote:\n> my order is late\n\n-- \nAna\nCompany")
    assert m.body == "Please check invoice INV-2026-0042."


def test_html_only_drops_blockquote_and_tags():
    m = mail(HEAD + "Subject: Hi\nContent-Type: text/html\n\n<html><head><style>p{}</style></head><body><p>Real <b>text</b></p>"
             "<blockquote>old history about refund</blockquote></body></html>")
    assert "Real text" in m.body and "refund" not in m.body and "<" not in m.body


def test_encoded_display_name_and_lowercased_address():
    raw = ("From: =?utf-8?q?Zo=C3=AB_M=C3=BCller?= <Zoe.Mueller@Example.com>\nTo: support@shop.example\n"
           "Date: Mon, 02 Mar 2026 09:00:00 +0000\nMessage-ID: <x@example.com>\nSubject: =?utf-8?q?Caf=C3=A9?=\n\nhi")
    m = parse_bytes(raw.encode())
    assert m.sender_name == "Zoë Müller" and m.sender == "zoe.mueller@example.com" and m.subject == "Café"


def test_missing_message_id_gets_stable_derived_id():
    raw = b"From: a@example.com\nDate: Mon, 02 Mar 2026 09:00:00 +0000\nSubject: x\n\nbody"
    assert parse_bytes(raw).message_id == parse_bytes(raw).message_id
    assert parse_bytes(raw).message_id.startswith("<sha256-")


def test_unparseable_date_falls_back_to_epoch_not_crash():
    m = parse_bytes(b"From: a@example.com\nDate: not a date\nMessage-ID: <d@example.com>\nSubject: x\n\nb")
    assert m.sent_at.startswith("1970-01-01")


def test_dsn_is_flagged_and_final_recipient_available():
    m = mail("From: Mail Delivery System <MAILER-DAEMON@mx.example.net>\nTo: support@shop.example\nDate: Mon, 02 Mar 2026 09:00:00 +0000\n"
             "Message-ID: <b@mx.example.net>\nReturn-Path: <>\nContent-Type: multipart/report; report-type=delivery-status; boundary=\"B\"\n\n"
             "--B\nContent-Type: text/plain\n\nfailed\n--B\nContent-Type: message/delivery-status\n\nReporting-MTA: dns; mx\n\n"
             "Final-Recipient: rfc822; gone@example.org\nAction: failed\n\n--B--\n")
    assert m.flags["is_dsn"] and "gone@example.org" in m.dsn_text
