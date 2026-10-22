"""The second look at automated mail that carries no standard marker (guard.py, roles.py) and the machine-mail format sets."""
import hashlib
from pathlib import Path

import pytest

from mailtriage import datagen_formats
from mailtriage.classify import classify
from mailtriage.datagen import MACHINE, OWN, read_labels
from mailtriage.evaluate import sink_replies
from mailtriage.guard import looks_automated
from mailtriage.harness import SinkProcess, run_cli
from mailtriage.parse import parse_file
from mailtriage.roles import role_account

from conftest import HEAD, mail


def msg(subject: str, body: str, sender: str = "ana@example.com"):
    return mail(HEAD.replace("ana@example.com", sender) + f"Subject: {subject}\n\n{body}\n")


def test_wording_guard_flags_unmarked_leave_notices_and_receipts():
    leave = msg("Re: Order question", "Thanks for your email. I am on annual leave until 14 May and will respond when I return.")
    receipt = msg("Your receipt from Acme", "Amount paid: $48.00\nPayment method: card ending 4242", "receipts@pay.example.com")
    assert looks_automated(leave).automated and "leave notice" in looks_automated(leave).cues
    assert looks_automated(receipt).automated


def test_wording_guard_leaves_ordinary_customer_wording_alone():
    # the phrases that first made it over-eager: a customer mentioning their payment method or a possible unsubscribe
    refund = msg("I want my money back", "Please cancel order ORD-96994 and refund $45.00 to my original payment method. "
                                         "I will unsubscribe from the newsletter if this continues.")
    shipped = msg("Where is ORD-31897?", "Has my order shipped yet? I would like the tracking number.")
    assert not looks_automated(refund).automated
    assert not looks_automated(shipped).automated  # one medium cue alone is below the threshold


def test_role_rule_flags_role_addresses_and_not_people():
    for local in ("billing", "orders", "notify", "hello", "support", "receipts", "help-desk", "alerts42", "no-reply"):
        assert role_account(msg("Hi", "text", f"{local}@example.com")), local
    for local in ("ava.mueller", "soren.nielsen12", "zoe", "priya.patel", "marek"):
        assert not role_account(msg("Hi", "text", f"{local}@example.com")), local


def test_guards_never_hold_a_human_message_in_the_generated_main_sets(small_set):
    labels = {r["file"]: r for r in read_labels(small_set / "labels.csv")}
    held = 0
    for f, lab in labels.items():
        if lab["category"] in MACHINE:
            continue
        m = parse_file(small_set / "inbox" / f)
        if classify(m, OWN).reply_eligible and (looks_automated(m).automated or role_account(m)):
            held += 1
    assert held == 0


@pytest.fixture(scope="module", params=datagen_formats.SET_NAMES)
def format_set(request, tmp_path_factory):
    out = tmp_path_factory.mktemp(request.param)
    info = datagen_formats.generate_formats(out, request.param)
    return request.param, out, info


def test_format_sets_regenerate_byte_for_byte(format_set, tmp_path):
    name, out, info = format_set
    again = datagen_formats.generate_formats(tmp_path, name)
    assert again["sha256"] == info["sha256"]
    committed = Path(__file__).resolve().parents[1] / "data" / name / "MANIFEST.sha256"
    if committed.exists():  # the committed copy is what the published numbers were measured on
        assert hashlib.sha256(committed.read_bytes()).hexdigest() == info["sha256"]


def test_format_sets_are_all_machine_mail_with_unique_senders(format_set):
    name, out, info = format_set
    rows = read_labels(out / "labels.csv")
    assert len(rows) == 196 and all(r["expect_reply"] == "0" for r in rows)
    assert {int(r["marked"]) for r in rows} == {0, 1}
    senders = [parse_file(out / "inbox" / r["file"]).sender for r in rows]
    assert len(set(senders)) == len(senders)  # the 24 h cooldown can never hide a wrongly answered message


def test_messages_labelled_marked_really_are_caught_by_the_standard_markers(format_set):
    name, out, _ = format_set
    for r in read_labels(out / "labels.csv"):
        if r["marked"] == "1":
            d = classify(parse_file(out / "inbox" / r["file"]), OWN)
            assert not d.reply_eligible and d.category in MACHINE, (r["format"], d.category)


def run_inbox(inbox: Path, work: Path, guard: str):
    work.mkdir(parents=True)
    with SinkProcess(work / "sink") as sink:
        r = run_cli(["run", "--inbox", str(inbox), "--db", str(work / "s.sqlite"), "--smtp-port", str(sink.port),
                     "--sink-dir", str(work / "sink"), "--guard", guard], timeout=120)
    assert r.returncode == 0, r.stderr
    return [x["in_reply_to"] for x in sink_replies(work / "sink")]


def test_pipeline_holds_unmarked_automated_mail_for_review_instead_of_replying(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.eml").write_bytes(
        (HEAD.replace("ana@example.com", "receipts@pay.example.com").replace("<t1@", "<receipt@")
         + "Subject: Your receipt from Acme\n\nAmount paid: $48.00\nPayment method: card ending 4242\n").encode())
    (inbox / "b.eml").write_bytes(
        (HEAD.replace("<t1@", "<human@") + "Subject: Where is my order\n\nHello, where is my order ORD-31897? Any tracking?\n").encode())
    off = run_inbox(inbox, tmp_path / "off", "off")
    full = run_inbox(inbox, tmp_path / "full", "full")
    assert sorted(off) == ["<human@example.com>", "<receipt@example.com>"]  # without the guard the receipt is answered
    assert full == ["<human@example.com>"]  # with it, only the person is
