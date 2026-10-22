"""`python -m mailtriage reproduce`: data -> tests -> evaluation -> baseline -> crash campaigns -> results/."""
from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from . import __version__, crashtest, datagen, datagen_formats
from .evaluate import run_clean, score_replies
from .pipeline import GUARD_LEVELS

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
log = logging.getLogger("reproduce")

SEEDS = {"targeted": 7, "random": 11}
KILLS = {"targeted": 60, "random": 40, "naive": 54}
# Measured: at 12 ms the campaign reached only 38-39 of its 40 kills in 3 of 3 repeats (the run finishes before the last kill
# lands); at 25 ms it reached 40 in 3 of 3.
RANDOM_DELAY_MS = 25


def _data_step(cfg: dict) -> dict:
    final = ROOT / "data" / cfg["name"]
    tmp = ROOT / "results" / f".regen-{cfg['name']}"
    if tmp.exists():
        shutil.rmtree(tmp)
    info = datagen.generate(tmp, cfg["n"], cfg["seed"], cfg["holdout_share"], cfg["name"])
    new_manifest = (tmp / "MANIFEST.sha256").read_text()
    old = final / "MANIFEST.sha256"
    identical = old.exists() and old.read_text() == new_manifest
    if not identical:
        if final.exists():
            shutil.rmtree(final)
        shutil.copytree(tmp, final)
    shutil.rmtree(tmp)
    rows = [r for r in datagen.read_labels(final / "labels.csv")]
    uniq = [r for r in rows if r["is_duplicate"] == "0"]
    return {"files": len(rows), "unique_messages": len(uniq), "redelivered_copies": len(rows) - len(uniq),
            "seed": cfg["seed"], "holdout_phrasing_share": cfg["holdout_share"],
            "categories": dict(Counter(r["category"] for r in uniq)),
            "challenge_messages": sum(int(r["challenge"]) for r in uniq),
            "manifest_sha256": hashlib.sha256(new_manifest.encode()).hexdigest(),
            "regenerated_byte_identical_to_committed": identical}


def _formats_data_step(name: str) -> dict:
    final = ROOT / "data" / name
    tmp = ROOT / "results" / f".regen-{name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    info = datagen_formats.generate_formats(tmp, name)
    new_manifest = (tmp / "MANIFEST.sha256").read_text()
    old = final / "MANIFEST.sha256"
    identical = old.exists() and old.read_text() == new_manifest
    if not identical:
        if final.exists():
            shutil.rmtree(final)
        shutil.copytree(tmp, final)
    shutil.rmtree(tmp)
    rows = datagen.read_labels(final / "labels.csv")
    return {"files": len(rows), "formats": info["n_formats"], "marked": sum(int(r["marked"]) for r in rows),
            "unmarked": sum(1 - int(r["marked"]) for r in rows), "seed": info["seed"],
            "manifest_sha256": hashlib.sha256(new_manifest.encode()).hexdigest(),
            "regenerated_byte_identical_to_committed": identical}


def _rules_frozen() -> bool:
    frozen = {ln.split()[1]: ln.split()[0] for ln in (ROOT / "data" / "RULES_FROZEN.sha256").read_text().splitlines()
              if ln and not ln.startswith("#")}
    return all(hashlib.sha256((ROOT / "src" / "mailtriage" / n).read_bytes()).hexdigest() == h for n, h in frozen.items())


def _pytest() -> dict:
    junit = RESULTS / "pytest-junit.xml"
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, "-m", "pytest", "--junitxml", str(junit), "-q"], cwd=ROOT, capture_output=True, text=True)
    (RESULTS / "pytest-output.txt").write_text(r.stdout + r.stderr)
    suite = ET.parse(junit).getroot()
    suite = suite if suite.tag == "testsuite" else suite[0]
    n = int(suite.get("tests")); bad = int(suite.get("failures")) + int(suite.get("errors"))
    return {"tests": n, "passed": n - bad - int(suite.get("skipped")), "failed": bad, "skipped": int(suite.get("skipped")),
            "seconds": round(time.perf_counter() - t0, 1)}


def _strip(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "sink_dir"}


def reproduce() -> int:
    RESULTS.mkdir(exist_ok=True)
    fh = logging.FileHandler(RESULTS / "run.log", mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(logging.INFO)
    started = datetime.now(timezone.utc)
    res: dict = {"meta": {"project": "email-automation-triage-autoreply", "version": __version__,
                          "started_utc": started.isoformat(timespec="seconds"), "python": platform.python_version(),
                          "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
                          "cpus": __import__("os").cpu_count(), "aiosmtpd": metadata.version("aiosmtpd"),
                          "pytest": metadata.version("pytest"), "sqlite": __import__("sqlite3").sqlite_version}}
    dur: dict = {}

    def step(name, fn):
        t = time.perf_counter()
        log.info("== %s", name)
        out = fn()
        dur[name] = round(time.perf_counter() - t, 1)
        return out

    res["data"] = {c["name"]: step(f"data:{c['name']}", lambda c=c: _data_step(c)) for c in (datagen.DEV, datagen.TEST)}
    res["data"].update({n: step(f"data:{n}", lambda n=n: _formats_data_step(n)) for n in datagen_formats.SET_NAMES})
    res["rules_unchanged_since_freeze"] = _rules_frozen()
    log.info("rules unchanged since freeze: %s", res["rules_unchanged_since_freeze"])
    res["tests"] = step("pytest", _pytest)
    log.info("tests: %s", res["tests"])

    dev = step("clean run: dev", lambda: run_clean(ROOT / "data" / "dev", RESULTS / ".work" / "dev"))
    test = step("clean run: test", lambda: run_clean(ROOT / "data" / "test", RESULTS / ".work" / "test"))
    expected = set(test["replied"])
    res["classification"] = {"dev": dev["score"], "test": test["score"]}
    res["guard_on_main_sets"] = {"dev_held_for_review": dev["run"]["triage"].get("guard_held_for_review", 0),
                                 "test_held_for_review": test["run"]["triage"].get("guard_held_for_review", 0)}
    res["throughput"] = {"messages_parsed": res["data"]["test"]["files"], **test["run"]["seconds"],
                         "replies_sent": len(expected),
                         "messages_per_second_ingest_parse": round(res["data"]["test"]["files"] / test["run"]["seconds"]["ingest_parse"], 1),
                         "replies_per_second_smtp": round(len(expected) / test["run"]["seconds"]["send"], 1)}

    naive = step("clean run: naive baseline", lambda: run_clean(ROOT / "data" / "test", RESULTS / ".work" / "naive", naive=True))
    labels = ROOT / "data" / "test" / "labels.csv"
    res["baseline_vs_pipeline"] = {"naive_responder": score_replies(naive["replied"], labels),
                                   "pipeline": score_replies(test["replied"], labels)}

    # machine mail in formats the rules were not written for, at each guard level (real pipeline, real SMTP)
    res["machine_mail_formats"] = {
        n: {g: step(f"formats {n}, guard={g}", lambda n=n, g=g: run_clean(
            ROOT / "data" / n, RESULTS / ".work" / f"{n}-{g}", formats=True, guard=g)["score"]) for g in GUARD_LEVELS}
        for n in datagen_formats.SET_NAMES}

    crash = {}
    crash["pipeline_targeted"] = step("crash: pipeline targeted", lambda: crashtest.targeted(
        ROOT / "data" / "test", RESULTS / ".work" / "ct", KILLS["targeted"], SEEDS["targeted"], expected))
    crash["pipeline_random_wall_clock"] = step("crash: pipeline random", lambda: crashtest.random_kills(
        ROOT / "data" / "test", RESULTS / ".work" / "cr", SEEDS["random"], expected, KILLS["random"], RANDOM_DELAY_MS))
    crash["naive_targeted"] = step("crash: naive targeted", lambda: crashtest.targeted(
        ROOT / "data" / "test", RESULTS / ".work" / "cn", KILLS["naive"], SEEDS["targeted"], set(naive["replied"]), naive=True))
    naive_clean_dups = res["baseline_vs_pipeline"]["naive_responder"]["duplicate_replies"]
    crash["naive_targeted"]["duplicates_caused_by_crashes"] = crash["naive_targeted"]["delivery"]["duplicates"] - naive_clean_dups
    res["crash_tests"] = {k: _strip(v) for k, v in crash.items()}
    (RESULTS / "crash").mkdir(exist_ok=True)
    for k, v in res["crash_tests"].items():
        (RESULTS / "crash" / f"{k}.json").write_text(json.dumps(v, indent=2))

    out = RESULTS / "outputs" / "test"
    if out.exists():
        shutil.rmtree(out)
    (out / "sample-replies").mkdir(parents=True)
    work = RESULTS / ".work" / "test"
    shutil.copy(work / "triage.csv", out / "triage.csv")
    shutil.copy(work / "sink" / "ledger.jsonl", out / "ledger.jsonl")
    for p in sorted((work / "sink" / "inbox").glob("*.eml"))[:5]:
        shutil.copy(p, out / "sample-replies" / p.name)
    shutil.rmtree(RESULTS / ".work")

    res["meta"]["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["meta"]["step_seconds"] = dur
    (RESULTS / "results.json").write_text(json.dumps(res, indent=2))
    from .report import update_readme
    update_readme(res)
    c = res["crash_tests"]
    log.info("DONE. tests %s/%s passed | test accuracy %.1f%% | targeted kills %d dup %d lost %d | random kills %d dup %d lost %d",
             res["tests"]["passed"], res["tests"]["tests"], 100 * res["classification"]["test"]["category_accuracy"],
             c["pipeline_targeted"]["kills_delivered"], c["pipeline_targeted"]["delivery"]["duplicates"],
             c["pipeline_targeted"]["delivery"]["lost"], c["pipeline_random_wall_clock"]["kills_delivered"],
             c["pipeline_random_wall_clock"]["delivery"]["duplicates"], c["pipeline_random_wall_clock"]["delivery"]["lost"])
    return 0 if res["tests"]["failed"] == 0 else 1
