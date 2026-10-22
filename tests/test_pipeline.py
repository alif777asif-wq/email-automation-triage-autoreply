import json
import sqlite3
from pathlib import Path

import pytest

from mailtriage import datagen
from mailtriage.evaluate import sink_replies
from mailtriage.harness import SinkProcess, run_cli
from mailtriage.parse import parse_bytes
from mailtriage.store import Store


@pytest.fixture()
def env(tmp_path, small_set):
    with SinkProcess(tmp_path / "sink") as sink:
        yield dict(set=small_set, work=tmp_path, sink=sink,
                   args=["run", "--inbox", str(small_set / "inbox"), "--db", str(tmp_path / "s.sqlite"),
                         "--smtp-port", str(sink.port), "--sink-dir", str(tmp_path / "sink")])


def counts(work):
    con = sqlite3.connect(str(work / "s.sqlite"))
    out = dict(con.execute("SELECT state, COUNT(*) FROM mail GROUP BY state"))
    con.close()
    return out


def test_rerun_is_idempotent_and_never_resends(env):
    assert run_cli(env["args"]).returncode == 0
    first = len(sink_replies(env["work"] / "sink"))
    assert first > 0
    assert run_cli(env["args"]).returncode == 0 and run_cli(env["args"]).returncode == 0
    assert len(sink_replies(env["work"] / "sink")) == first
    assert counts(env["work"]).get("SENT") == first


def test_redelivered_messages_are_processed_once(env):
    run_cli(env["args"])
    dups = sum(1 for r in datagen.read_labels(env["set"] / "labels.csv") if r["is_duplicate"] == "1")
    st = Store(env["work"] / "s.sqlite")
    assert st.db.execute("SELECT COUNT(*) FROM files WHERE duplicate=1").fetchone()[0] == dups
    assert st.db.execute("SELECT COUNT(*) FROM mail").fetchone()[0] == st.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] - dups


def test_no_reply_is_ever_sent_to_machine_senders_or_inside_cooldown(env):
    run_cli(env["args"])
    labels = {r["message_id"]: r for r in datagen.read_labels(env["set"] / "labels.csv") if r["is_duplicate"] == "0"}
    for r in sink_replies(env["work"] / "sink"):
        assert labels[r["in_reply_to"]]["category"] not in ("auto_reply", "bounce", "bulk")
        assert r["auto_submitted"] == "auto-replied"


def _stuck_in_sending(env):
    """Run once, then rewind one SENT row to SENDING, as if the process died right after the SMTP call."""
    run_cli(env["args"])
    st = Store(env["work"] / "s.sqlite")
    mid = st.db.execute("SELECT message_id FROM mail WHERE state='SENT' LIMIT 1").fetchone()[0]
    st.db.execute("UPDATE mail SET state='SENDING' WHERE message_id=?", (mid,))
    return st, mid


def test_sending_row_found_in_ledger_is_marked_sent_not_resent(env):
    st, mid = _stuck_in_sending(env)
    before = len(sink_replies(env["work"] / "sink"))
    st.close()
    run_cli(env["args"])
    assert len(sink_replies(env["work"] / "sink")) == before
    assert Store(env["work"] / "s.sqlite").db.execute("SELECT state FROM mail WHERE message_id=?", (mid,)).fetchone()[0] == "SENT"


def test_sending_row_missing_from_ledger_is_sent_exactly_once(env):
    st, mid = _stuck_in_sending(env)
    before = len(sink_replies(env["work"] / "sink"))
    st.close()
    (env["work"] / "sink" / "ledger.jsonl").write_text("")  # ledger says: nothing was delivered
    run_cli(env["args"])
    assert len(sink_replies(env["work"] / "sink")) == before + 1  # the (test-erased) delivery is re-sent once


def test_unavailable_ledger_sends_ambiguous_rows_to_manual_review_not_blind_resend(env):
    st, mid = _stuck_in_sending(env)
    before = len(sink_replies(env["work"] / "sink"))
    st.close()
    (env["work"] / "sink" / "ledger.jsonl").unlink()
    run_cli(env["args"])
    assert Store(env["work"] / "s.sqlite").db.execute("SELECT state FROM mail WHERE message_id=?", (mid,)).fetchone()[0] == "REVIEW"
    assert len(sink_replies(env["work"] / "sink")) == before


def test_illegal_state_transition_is_refused(tmp_path):
    st = Store(tmp_path / "x.sqlite")
    st.add_received(parse_bytes(b"From: a@example.com\nDate: Mon, 02 Mar 2026 09:00:00 +0000\nMessage-ID: <z@x>\nSubject: s\n\nb", "f.eml"))
    with pytest.raises(RuntimeError):
        st.transition("<z@x>", "SENT", "SENDING")  # cannot skip QUEUED/SENDING


def test_unreachable_smtp_server_leaves_mail_queued_not_lost(tmp_path, small_set):
    args = ["run", "--inbox", str(small_set / "inbox"), "--db", str(tmp_path / "s.sqlite"), "--smtp-port", "1",
            "--sink-dir", str(tmp_path / "sink")]
    run_cli(args)
    c = counts(tmp_path)
    assert c.get("SENT", 0) == 0 and c.get("QUEUED", 0) > 0 and "FAILED" not in c
