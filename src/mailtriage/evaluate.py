"""Scoring against ground truth and delivery verification against what the SMTP sink actually received."""
from __future__ import annotations

import json
import shutil
import sqlite3
from collections import Counter, defaultdict
from email import policy
from email.parser import BytesParser
from pathlib import Path

from .datagen import MACHINE, QUEUE, REPLY_CATS, read_labels
from .harness import SinkProcess, run_cli

CATS = ["billing", "order_status", "tech_support", "sales_lead", "refund_request", "unsubscribe", "auto_reply",
        "bounce", "bulk"]


def sink_replies(sink_dir: Path) -> list[dict]:
    out = []
    for p in sorted((Path(sink_dir) / "inbox").glob("*.eml")):
        m = BytesParser(policy=policy.default).parsebytes(p.read_bytes(), headersonly=True)
        out.append({"file": p.name, "in_reply_to": str(m["In-Reply-To"] or ""), "to": str(m["To"] or ""),
                    "message_id": str(m["Message-ID"] or ""), "auto_submitted": str(m["Auto-Submitted"] or "")})
    return out


def verify_delivery(sink_dir: Path, expected: set[str]) -> dict:
    """Count from the delivered files themselves: duplicates, lost, unexpected."""
    counts = Counter(r["in_reply_to"] for r in sink_replies(sink_dir))
    return {"delivered_total": sum(counts.values()), "delivered_unique": len(counts),
            "duplicates": sum(c - 1 for c in counts.values() if c > 1),
            "messages_answered_twice_or_more": sum(1 for c in counts.values() if c > 1),
            "lost": len(expected - set(counts)), "unexpected": len(set(counts) - expected)}


def db_rows(db: Path) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM mail").fetchall()
    con.close()
    return rows


def score_run(db: Path, labels_path: Path, sink_dir: Path) -> dict:
    labels = {r["message_id"]: r for r in read_labels(labels_path) if not int(r["is_duplicate"])}
    rows = {r["message_id"]: r for r in db_rows(db)}
    n = len(labels)
    missing = [m for m in labels if m not in rows]
    conf: dict = defaultdict(Counter)
    for mid, lab in labels.items():
        conf[lab["category"]][rows[mid]["category"] if mid in rows else "unprocessed"] += 1
    correct = sum(conf[c][c] for c in CATS)
    per_class, f1s = {}, []
    for c in CATS:
        support = sum(conf[c].values())
        predicted = sum(conf[t][c] for t in CATS)
        tp = conf[c][c]
        prec, rec = (tp / predicted if predicted else 0.0), (tp / support if support else 0.0)
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[c] = {"support": support, "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}
        f1s.append(f1)
    queue_ok = sum(1 for m, l in labels.items() if m in rows and rows[m]["queue"] == l["queue"])
    review = sum(1 for m in labels if m in rows and rows[m]["category"] == "unknown")
    hard = [m for m, l in labels.items() if int(l["challenge"])]
    hard_ok = sum(1 for m in hard if m in rows and rows[m]["category"] == labels[m]["category"])
    def subset(keys):
        keys = [m for m in keys if m in labels]
        ok = sum(1 for m in keys if m in rows and rows[m]["category"] == labels[m]["category"])
        rev = sum(1 for m in keys if m in rows and rows[m]["category"] == "unknown")
        return {"n": len(keys), "correct": ok, "accuracy": round(ok / len(keys), 4) if keys else None,
                "manual_review": rev, "misrouted_not_review": len(keys) - ok - rev}

    human_seen = [m for m, l in labels.items() if l["phrasing"] == "A"]
    human_unseen = [m for m, l in labels.items() if l["phrasing"] == "B"]
    unseen_recall = {}
    for c in CATS[:6]:
        ks = [m for m in human_unseen if labels[m]["category"] == c]
        ok = sum(1 for m in ks if rows[m]["category"] == c)
        unseen_recall[c] = {"n": len(ks), "correct": ok, "recall": round(ok / len(ks), 4) if ks else None}
    by_phrasing = {"machine_mail": subset([m for m, l in labels.items() if l["category"] in MACHINE]),
                   "human_seen_wording": subset(human_seen), "human_unseen_wording": subset(human_unseen),
                   "human_unseen_wording_recall": unseen_recall}
    # field extraction
    exp = got = spurious = 0
    for mid, lab in labels.items():
        f = json.loads(rows[mid]["fields"] or "{}") if mid in rows else {}
        for key in ("order_id", "invoice_no", "amount", "bounced_address"):
            if lab[key]:
                exp += 1
                got += int(f.get(key) == lab[key])
            elif key in f and key != "bounced_address":
                spurious += 1
    # reply policy, scored on what the SMTP sink received
    replied = Counter(r["in_reply_to"] for r in sink_replies(sink_dir))
    expect = {m for m, l in labels.items() if l["expect_reply"] == "1"}
    to_machines = sum(c for m, c in replied.items() if m in labels and labels[m]["category"] in MACHINE)
    missed = expect - set(replied)
    extra = {m for m in replied if m in labels} - expect
    cat_of = lambda m: rows[m]["category"] if m in rows else "unprocessed"  # noqa: E731
    return {
        "messages_scored": n, "unprocessed": len(missing),
        "category_accuracy": round(correct / n, 4), "macro_f1": round(sum(f1s) / len(f1s), 4),
        "queue_accuracy": round(queue_ok / n, 4), "manual_review": review, "manual_review_rate": round(review / n, 4),
        "misrouted_not_review": n - correct - review,
        "challenge": {"n": len(hard), "accuracy": round(hard_ok / len(hard), 4) if hard else None},
        "by_phrasing": by_phrasing, "per_class": per_class, "confusion": {c: dict(conf[c]) for c in CATS},
        "extraction": {"fields_expected": exp, "fields_correct": got, "accuracy": round(got / exp, 4) if exp else None,
                       "spurious_values": spurious},
        "reply_policy": {"expected_replies": len(expect), "replies_delivered_unique": len(replied),
                         "missed_replies": len(missed), "extra_replies": len(set(replied) - expect),
                         "duplicate_replies": sum(c - 1 for c in replied.values() if c > 1),
                         "replies_to_automated_senders": to_machines,
                         # what the missed and extra replies actually were
                         "missed_to_manual_review": sum(1 for m in missed if cat_of(m) == "unknown"),
                         "missed_treated_as_unsubscribe": sum(1 for m in missed if cat_of(m) == "unsubscribe"),
                         "missed_in_unseen_wording": sum(1 for m in missed if labels[m]["phrasing"] == "B"),
                         "extra_inside_cooldown": sum(1 for m in extra if labels[m]["expect_reason"] == "cooldown"),
                         "extra_to_unsubscribe_requests": sum(1 for m in extra if labels[m]["category"] == "unsubscribe"),
                         "acknowledged_under_wrong_topic": sum(1 for m in replied if m in labels and labels[m]["category"] in REPLY_CATS
                                                               and cat_of(m) != labels[m]["category"])},
    }


def score_formats(db: Path, labels_path: Path, sink_dir: Path) -> dict:
    """Machine-mail format sets: every message is machine mail, so the right outcome is never an automatic reply.

    replied   an acknowledgement was delivered to the sender (counted from the SMTP sink): the failure
    review    sent to a person, never auto-answered
    machine   recognised as an auto-reply, bounce or bulk mail
    other     classified as a human category that does not trigger a reply (an unsubscribe request)
    """
    labels = read_labels(labels_path)
    rows = {r["message_id"]: r for r in db_rows(db)}
    replied = Counter(r["in_reply_to"] for r in sink_replies(sink_dir))
    blank = lambda: {"n": 0, "replied": 0, "review": 0, "machine": 0, "other": 0}  # noqa: E731
    by_format: dict = {}
    groups = {"marked": blank(), "unmarked": blank(), "all": blank()}
    for lab in labels:
        row = rows.get(lab["message_id"])
        if replied.get(lab["message_id"]):
            outcome = "replied"
        elif row is None or row["category"] == "unknown":
            outcome = "review"
        elif row["category"] in MACHINE:
            outcome = "machine"
        else:
            outcome = "other"
        f = by_format.setdefault(lab["format"], {"category": lab["category"], "marked": int(lab["marked"]), **blank()})
        for tgt in (f, groups["marked" if lab["marked"] == "1" else "unmarked"], groups["all"]):
            tgt["n"] += 1
            tgt[outcome] += 1
    return {"messages": len(labels), "replies_to_automated_senders": sum(replied.values()), "groups": groups,
            "by_format": by_format}


def run_clean(set_dir: Path, work: Path, naive: bool = False, formats: bool = False, guard: str = "full") -> dict:
    """One uninterrupted run against a fresh sink; returns timing, scoring (pipeline) and the delivered-reply set."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sink_dir = work / "sink"
    with SinkProcess(sink_dir) as sink:
        args = ["run", "--inbox", str(Path(set_dir) / "inbox"), "--smtp-port", str(sink.port),
                "--sink-dir", str(sink_dir)]
        args += ["--naive", "--cursor", str(work / "cursor.txt")] if naive else \
            ["--db", str(work / "state.sqlite"), "--csv", str(work / "triage.csv")]
        if not naive:
            args += ["--guard", guard]
        r = run_cli(args, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"run failed: {r.stderr[-2000:]}")
    out = {"stdout": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", "sink_dir": str(sink_dir)}
    out["replied"] = Counter(x["in_reply_to"] for x in sink_replies(sink_dir))
    if formats:
        out["score"] = score_formats(work / "state.sqlite", Path(set_dir) / "labels.csv", sink_dir)
        out["run"] = json.loads(out["stdout"])
    elif not naive:
        out["score"] = score_run(work / "state.sqlite", Path(set_dir) / "labels.csv", sink_dir)
        out["run"] = json.loads(out["stdout"])
    return out


def score_replies(replied: Counter, labels_path: Path) -> dict:
    """Score any responder (used for the naive baseline) purely on what the SMTP sink received."""
    labels = {r["message_id"]: r for r in read_labels(labels_path) if not int(r["is_duplicate"])}
    expect = {m for m, l in labels.items() if l["expect_reply"] == "1"}
    return {"replies_delivered_total": sum(replied.values()),
            "replies_to_automated_senders": sum(c for m, c in replied.items() if m in labels and labels[m]["category"] in MACHINE),
            "replies_to_unsubscribe_requests": sum(c for m, c in replied.items() if m in labels and labels[m]["category"] == "unsubscribe"),
            "replies_inside_cooldown": sum(c for m, c in replied.items() if m in labels and labels[m]["expect_reason"] == "cooldown"),
            "duplicate_replies": sum(c - 1 for c in replied.values() if c > 1),
            "missed_replies": len(expect - set(replied))}
