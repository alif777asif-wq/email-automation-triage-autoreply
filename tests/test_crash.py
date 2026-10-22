import json
from collections import Counter
from pathlib import Path

from mailtriage import crashtest
from mailtriage.evaluate import run_clean, verify_delivery


def test_pipeline_survives_forced_kills_with_zero_duplicates_and_zero_loss(tmp_path, small_set):
    clean = run_clean(small_set, tmp_path / "clean")
    expected = set(clean["replied"])
    res = crashtest.targeted(small_set, tmp_path / "t", kills=18, seed=3, expected=expected, n_files=80)
    assert res["kills_delivered"] == 18
    assert res["delivery"]["duplicates"] == 0 and res["delivery"]["lost"] == 0 and res["delivery"]["unexpected"] == 0
    assert "SENDING" not in res["final_states"] and "REVIEW" not in res["final_states"]


def test_the_checker_can_fail_naive_responder_double_sends_after_a_crash(tmp_path, small_set):
    naive_clean = run_clean(small_set, tmp_path / "nc", naive=True)
    base_dups = sum(c - 1 for c in naive_clean["replied"].values() if c > 1)
    res = crashtest.targeted(small_set, tmp_path / "n", kills=12, seed=3, expected=set(naive_clean["replied"]),
                             naive=True, n_files=80)
    assert res["delivery"]["duplicates"] > base_dups  # kills between SMTP accept and cursor write => extra copies


def test_verifier_flags_a_planted_duplicate_and_a_planted_loss(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for i, rid in enumerate(["<a@x>", "<a@x>", "<b@x>"]):
        (inbox / f"{i:06d}.eml").write_bytes(f"From: s@example.com\nIn-Reply-To: {rid}\nMessage-ID: <r{i}@x>\n\nbody".encode())
    v = verify_delivery(tmp_path, expected={"<a@x>", "<b@x>", "<c@x>"})
    assert v["duplicates"] == 1 and v["lost"] == 1 and v["unexpected"] == 0
