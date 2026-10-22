"""Crash campaigns: kill the process with SIGKILL at the worst moments, restart, repeat; then audit the SMTP sink.

targeted: instrumented kill points (inside the send path: after the state commit but before SMTP, after SMTP accepted but
          before the SENT commit, after the SENT commit) chosen by a seeded schedule.
random:   an outside observer SIGKILLs the process at random wall-clock instants, across every stage.
Every campaign ends with one uninterrupted run so the system can finish, then the delivered files are counted.
"""
from __future__ import annotations

import random
import shutil
import sqlite3
import subprocess
import time
from collections import Counter
from pathlib import Path

from .evaluate import verify_delivery
from .harness import SinkProcess, popen_cli, run_cli

PIPELINE_SEND_POINTS = ["before_smtp", "after_smtp_before_commit", "after_sent_commit"]


def _args(set_dir: Path, work: Path, port: int, sink_dir: Path, naive: bool) -> list[str]:
    a = ["run", "--inbox", str(set_dir / "inbox"), "--smtp-port", str(port), "--sink-dir", str(sink_dir)]
    return a + (["--naive", "--cursor", str(work / "cursor.txt")] if naive else ["--db", str(work / "state.sqlite")])


def _db_counts(db: Path) -> dict:
    if not db.exists():
        return {}
    con = sqlite3.connect(str(db))
    rows = con.execute("SELECT state, COUNT(*) FROM mail GROUP BY state").fetchall()
    con.close()
    return dict(rows)


def _reconcile_counts(stderr_chunks: list[str]) -> dict:
    text = "\n".join(stderr_chunks)
    return {"already_delivered_not_resent": text.count("-> SENT (already delivered"),
            "never_delivered_resent": text.count("-> QUEUED (never delivered"),
            "sent_to_manual_review": text.count("-> REVIEW")}


def targeted(set_dir: Path, work: Path, kills: int, seed: int, expected: set[str] | None, naive: bool = False,
             n_files: int = 1200) -> dict:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rng = random.Random(seed)
    sink_dir = work / "sink"
    cap_early = max(1, min(40, n_files // 30))
    cap_send = max(1, min(8, n_files // 150))
    if naive:
        schedule = [PIPELINE_SEND_POINTS[i % 3] for i in range(kills)]
    else:
        schedule = ["after_ingest_row"] * 3 + ["after_triage_row"] * 3
        schedule += [PIPELINE_SEND_POINTS[i % 3] for i in range(max(0, kills - 6))]
        schedule = schedule[:kills]
    stderr: list[str] = []
    by_point: Counter = Counter()
    runs = achieved = 0
    t0 = time.perf_counter()
    with SinkProcess(sink_dir) as sink:
        args = _args(set_dir, work, sink.port, sink_dir, naive)
        for point in schedule:
            cap = cap_early if point.startswith(("after_ingest", "after_triage")) else cap_send
            r = run_cli(args, env={"MAILTRIAGE_CRASH": f"{point}:{rng.randint(1, cap)}"}, timeout=300)
            runs += 1
            stderr.append(r.stderr)
            if r.returncode == -9:
                achieved += 1
                by_point[point] += 1
            elif r.returncode == 0:
                break  # nothing left to do before the schedule ran out
            else:
                raise RuntimeError(f"unexpected exit {r.returncode}: {r.stderr[-1500:]}")
        final = run_cli(args, timeout=600)
        runs += 1
        stderr.append(final.stderr)
        if final.returncode != 0:
            raise RuntimeError(f"final run failed: {final.stderr[-1500:]}")
        delivery = verify_delivery(sink_dir, expected or set())
    out = {"mode": "targeted", "responder": "naive" if naive else "pipeline", "kills_delivered": achieved,
           "kills_by_point": dict(by_point), "process_runs": runs, "delivery": delivery,
           "seconds": round(time.perf_counter() - t0, 1), "sink_dir": str(sink_dir)}
    if not naive:
        out["final_states"] = _db_counts(work / "state.sqlite")
        out["reconciliation"] = _reconcile_counts(stderr)
    return out


def random_kills(set_dir: Path, work: Path, seed: int, expected: set[str], target_kills: int = 30,
                 send_delay_ms: int = 5) -> dict:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rng = random.Random(seed)
    sink_dir = work / "sink"
    stderr: list[str] = []
    achieved = runs = 0
    t0 = time.perf_counter()
    with SinkProcess(sink_dir) as sink:
        args = _args(set_dir, work, sink.port, sink_dir, naive=False)
        env = {"MAILTRIAGE_SEND_DELAY_MS": str(send_delay_ms)}
        while achieved < target_kills:
            proc = popen_cli(args, env=env)
            runs += 1
            try:
                _, err = proc.communicate(timeout=rng.uniform(0.25, 0.9))
                stderr.append(err)
                if proc.returncode != 0:
                    raise RuntimeError(f"unexpected exit {proc.returncode}: {err[-1500:]}")
                break  # finished on its own before the kill landed: work is complete
            except subprocess.TimeoutExpired:
                proc.kill()  # SIGKILL: no cleanup handlers, no flush
                _, err = proc.communicate()
                stderr.append(err)
                achieved += 1
        final = run_cli(args, timeout=600)
        runs += 1
        stderr.append(final.stderr)
        if final.returncode != 0:
            raise RuntimeError(f"final run failed: {final.stderr[-1500:]}")
        delivery = verify_delivery(sink_dir, expected)
    return {"mode": "random_wall_clock", "responder": "pipeline", "kills_delivered": achieved, "process_runs": runs,
            "send_delay_ms": send_delay_ms, "delivery": delivery, "final_states": _db_counts(work / "state.sqlite"),
            "reconciliation": _reconcile_counts(stderr), "seconds": round(time.perf_counter() - t0, 1),
            "sink_dir": str(sink_dir)}
