"""Render results.json into the markdown block that README.md embeds (copied from results, never typed)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render(res: dict) -> str:
    t = res["classification"]["test"]
    c = res["crash_tests"]
    b = res["baseline_vs_pipeline"]
    d = res["data"]["test"]
    tp = res["throughput"]
    bp = t["by_phrasing"]
    rows = "\n".join(f"| {k} | {v['support']} | {pct(v['precision'])} | {pct(v['recall'])} | {pct(v['f1'])} |"
                     for k, v in t["per_class"].items())
    tg, rd, nv = c["pipeline_targeted"], c["pipeline_random_wall_clock"], c["naive_targeted"]
    rp = t["reply_policy"]
    fm = res["machine_mail_formats"]
    fd = res["data"]
    held = fm["formats-c"]["full"]
    still = [f"`{k}` ({v['replied']} of {v['n']})" for k, v in held["by_format"].items() if v["replied"]]
    fmt_rows = "\n".join(
        f"| `{k}` | {'yes' if v['marked'] else 'no'} | {v['n']} | {v['replied']} | {v['review']} | {v['machine']} |"
        for k, v in held["by_format"].items())

    def frow(name, role):
        s = fm[name]
        g = s["full"]["groups"]
        return (f"| `{name}` | {role} | {g['marked']['replied']} of {g['marked']['n']} | {g['unmarked']['n']} | "
                f"{s['off']['groups']['unmarked']['replied']} | {s['wording']['groups']['unmarked']['replied']} | "
                f"{g['unmarked']['replied']} |")

    return f"""Measured on the generated **test** set ({d['unique_messages']:,} unique messages in {d['files']:,} files; seed {d['seed']}).
Python {res['meta']['python']}, {res['meta']['platform']}, {res['meta']['cpus']} CPU. Source: `results/results.json`.

**Delivery integrity (what the SMTP server actually received)**

| Test | Forced kills (SIGKILL) | Replies delivered | Duplicates | Lost |
|---|---:|---:|---:|---:|
| Pipeline, kill points inside the send path | {tg['kills_delivered']} | {tg['delivery']['delivered_unique']} of {b['pipeline']['replies_delivered_total']} | {tg['delivery']['duplicates']} | {tg['delivery']['lost']} |
| Pipeline, random wall-clock kills | {rd['kills_delivered']} | {rd['delivery']['delivered_unique']} of {b['pipeline']['replies_delivered_total']} | {rd['delivery']['duplicates']} | {rd['delivery']['lost']} |
| Naive responder, same kind of kills | {nv['kills_delivered']} | {nv['delivery']['delivered_unique']} unique | {nv['delivery']['duplicates']} ({nv['duplicates_caused_by_crashes']} caused by the kills) | {nv['delivery']['lost']} |

**Naive responder vs this pipeline, uninterrupted run on the same inbox**

| Metric | Naive | Pipeline |
|---|---:|---:|
| Replies sent to automated senders (auto-replies, bounces, newsletters) | {b['naive_responder']['replies_to_automated_senders']} | {b['pipeline']['replies_to_automated_senders']} |
| Replies sent inside the 24 h cooldown | {b['naive_responder']['replies_inside_cooldown']} | {b['pipeline']['replies_inside_cooldown']} |
| Duplicate replies (re-delivered messages) | {b['naive_responder']['duplicate_replies']} | {b['pipeline']['duplicate_replies']} |

The pipeline's {b['pipeline']['replies_inside_cooldown']} replies inside the cooldown window each follow an earlier message from the same sender that was sent to manual review, so no earlier acknowledgement existed (checked against `results/outputs/test/triage.csv`).

**What the pipeline did against the labels** (the "{tg['delivery']['delivered_unique']} of {b['pipeline']['replies_delivered_total']}" above counts replies the pipeline decided to send; the labels say which replies were wanted)

| | Messages | What they were |
|---|---:|---|
| Acknowledgement wanted | {rp['expected_replies']} | |
| Acknowledgement sent | {rp['replies_delivered_unique']} | every one delivered exactly once |
| Wanted but not sent | {rp['missed_replies']} | {rp['missed_to_manual_review']} sent to manual review (a person sees them); {rp['missed_treated_as_unsubscribe']} real requests treated as unsubscribe requests, so the sender went on the suppression list. All {rp['missed_in_unseen_wording']} are in wording the rules had never seen |
| Sent but not wanted | {rp['extra_replies']} | {rp['extra_inside_cooldown']} inside the cooldown window (see above); {rp['extra_to_unsubscribe_requests']} unsubscribe requests the rules did not recognise, all in unseen wording |
| Acknowledged under the wrong topic | {rp['acknowledged_under_wrong_topic']} | the reply names another team or topic than the message needed |

**Machine mail the rules were not written for.** The main test builds its machine mail from a few templates the guards were written
against, so its 100% says little about mail from systems the author never saw. Three further sets ({fd['formats-a']['formats']} formats
each, {fd['formats-a']['files']} messages per set, every message machine mail, every sender unique) measure that. A message "with markers"
carries a standard marker (Auto-Submitted, Precedence, List-* header, DSN structure, or a mailer-daemon, postmaster, no-reply or
notifications sender). The right outcome for every message is no automatic reply. Replies sent to the messages without markers:

| Set | Role | Answered, with markers | Messages without markers | No guard | Wording guard | Wording guard + sender-role rule |
|---|---|---:|---:|---:|---:|---:|
{frow('formats-a', 'development set of the wording guard')}
{frow('formats-b', 'held out for the wording guard; development set of the role rule')}
{frow('formats-c', '**held out for the whole guard**')}

The guards (`guard.py`, then `roles.py`) were each frozen by hash before the next set was written (`data/RULES_FROZEN.sha256`). Neither changed
the main-test numbers: they held {res['guard_on_main_sets']['test_held_for_review']} of the {d['unique_messages']:,} test messages for review (and {res['guard_on_main_sets']['dev_held_for_review']} in dev). Messages a guard holds go to manual review,
never to a reply and never silently dropped.

On the held-out set, {held['groups']['unmarked']['replied']} of {held['groups']['unmarked']['n']} automated messages without markers still got an acknowledgement. The formats that still get through:
{', '.join(still)}. Every message with a marker went unanswered ({held['groups']['marked']['replied']} of {held['groups']['marked']['n']}).

| `formats-c` format | Has markers | Messages | Answered | To a person | Recognised as machine mail |
|---|---|---:|---:|---:|---:|
{fmt_rows}

**Triage** (rules frozen before the second phrase bank was written; about half of the human messages in the test set use that unseen wording)

| Subset | Messages | Correct | Sent to manual review | Wrong |
|---|---:|---:|---:|---:|
| Machine mail (headers and markers) | {bp['machine_mail']['n']} | {pct(bp['machine_mail']['accuracy'])} | {bp['machine_mail']['manual_review']} | {bp['machine_mail']['misrouted_not_review']} |
| Human mail, wording the rules had seen | {bp['human_seen_wording']['n']} | {pct(bp['human_seen_wording']['accuracy'])} | {bp['human_seen_wording']['manual_review']} | {bp['human_seen_wording']['misrouted_not_review']} |
| **Human mail, wording the rules had never seen** | {bp['human_unseen_wording']['n']} | **{pct(bp['human_unseen_wording']['accuracy'])}** | {bp['human_unseen_wording']['manual_review']} | {bp['human_unseen_wording']['misrouted_not_review']} |
| All | {t['messages_scored']} | {pct(t['category_accuracy'])} | {t['manual_review']} | {t['misrouted_not_review']} |

| Category (whole test set) | Messages | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
{rows}

Macro-F1 {t['macro_f1']:.3f}. Challenge subset ({t['challenge']['n']} messages with distractors, typos or header-less machine mail): {pct(t['challenge']['accuracy'])}.
Field extraction (order id, invoice number, amount, bounced address): {t['extraction']['fields_correct']} of {t['extraction']['fields_expected']} exact ({pct(t['extraction']['accuracy'])}).
Throughput, one run: {tp['messages_per_second_ingest_parse']} messages/s parsed, {tp['replies_per_second_smtp']} replies/s over local SMTP.
Tests: {res['tests']['passed']} of {res['tests']['tests']} passed."""


def update_readme(res: dict) -> None:
    block = f"{START}\n{render(res)}\n{END}"
    (ROOT / "results" / "results-table.md").write_text(render(res) + "\n")
    readme = ROOT / "README.md"
    if readme.exists() and START in readme.read_text():
        text = readme.read_text()
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        readme.write_text(head + block + tail)
