"""Command line: generate | run | sink | evaluate | crashtest | reproduce."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import datagen

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mailtriage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="(re)generate the synthetic dev/test data sets")
    g.add_argument("--set", choices=["dev", "test", "formats-a", "formats-b", "all"], default="all")
    g.add_argument("--out", default=str(ROOT / "data"))
    r = sub.add_parser("run", help="process an inbox once (idempotent; safe to kill and restart)")
    r.add_argument("--inbox", required=True)
    r.add_argument("--db")
    r.add_argument("--smtp-host", default="127.0.0.1")
    r.add_argument("--smtp-port", type=int, required=True)
    r.add_argument("--sink-dir", required=True, help="directory of the SMTP sink whose ledger is used for reconciliation")
    r.add_argument("--csv")
    r.add_argument("--naive", action="store_true", help="run the naive baseline responder instead")
    r.add_argument("--guard", choices=["off", "wording", "full"], default="full",
                   help="second look at mail that carries no standard machine marker: off | wording (guard.py) | full (+ roles.py)")
    r.add_argument("--cursor")
    sub.add_parser("reproduce", help="regenerate data, run tests, evaluation and crash campaigns -> results/")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s")

    if a.cmd == "generate":
        for cfg in (datagen.DEV, datagen.TEST):
            if a.set in (cfg["name"], "all"):
                info = datagen.generate(Path(a.out) / cfg["name"], cfg["n"], cfg["seed"], cfg["holdout_share"], cfg["name"])
                print(json.dumps(info))
        from . import datagen_formats
        for name in datagen_formats.SET_NAMES:
            if a.set in (name, "all"):
                print(json.dumps(datagen_formats.generate_formats(Path(a.out) / name, name)))
    elif a.cmd == "run":
        if a.naive:
            from .naive import run_naive
            print(json.dumps(run_naive(Path(a.inbox), Path(a.cursor), a.smtp_host, a.smtp_port)))
        else:
            from .pipeline import export_csv, run_pipeline
            res = run_pipeline(Path(a.inbox), Path(a.db), (a.smtp_host, a.smtp_port), Path(a.sink_dir),
                               guard=a.guard)
            if a.csv:
                from .store import Store
                st = Store(a.db)
                export_csv(st, Path(a.csv))
                st.close()
            print(json.dumps(res))
    elif a.cmd == "reproduce":
        from .reproduce import reproduce
        return reproduce()
    return 0
