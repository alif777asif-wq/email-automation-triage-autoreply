"""Generate the Upwork entry sheet and DELIVERY-NOTES.md from results.json, provenance.json and export-report.json."""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
R = json.loads((ROOT / "results" / "results.json").read_text())
PROV = json.loads((HERE / "provenance.json").read_text())
EXP = json.loads((HERE / "export-report.json").read_text())
AUD = json.loads((HERE / "contrast-audit.json").read_text())
FRESH = json.loads((HERE / "fresh-run-check.json").read_text())
HYGIENE = FRESH["hygiene_scan"]
assert FRESH["mismatches"] == [] and FRESH["fields_matched"] == FRESH["fields_compared"], FRESH

c, b = R["crash_tests"], R["baseline_vs_pipeline"]
t, d = R["classification"]["test"], R["data"]["test"]
bp = t["by_phrasing"]
kt, kr = c["pipeline_targeted"]["kills_delivered"], c["pipeline_random_wall_clock"]["kills_delivered"]
kills = kt + kr
n_msgs, replies = d["unique_messages"], b["pipeline"]["replies_delivered_total"]
nd, nb = b["naive_responder"]["duplicate_replies"] + c["naive_targeted"]["duplicates_caused_by_crashes"], b["naive_responder"]["replies_to_automated_senders"]
unseen = bp["human_unseen_wording"]
rp = t["reply_policy"]
fm = R["machine_mail_formats"]
fc = fm["formats-c"]["full"]["groups"]["unmarked"]            # the held-out set: nothing was tuned on it
kp = c["pipeline_targeted"]["kills_by_point"]
n_unsub = d["categories"]["unsubscribe"]

TITLE = "Email Automation: Crash-Safe Auto-Reply"
DESC = (f"Inbound-email triage and auto-reply pipeline in Python that avoids the usual failures: double-sent replies, "
        f"answers to automated mail, and lost work after a restart. On {n_msgs:,} generated messages over real SMTP, "
        f"{kills} forced process kills left {c['pipeline_targeted']['delivery']['duplicates']} duplicate replies and "
        f"{c['pipeline_targeted']['delivery']['lost']} lost; a naive responder produced {nd} duplicates ({c['naive_targeted']['kills_delivered']} kills) and {nb} replies to automated "
        f"senders. Keyword triage is a baseline: uncertain mail goes to a person, and automated mail with no standard marker can still get a reply.")
SHORT = (f"Python email triage and auto-reply pipeline that survives crashes: after {kills} forced process kills, 0 duplicate replies "
         f"and 0 lost (naive responder: {nd} duplicates in {c['naive_targeted']['kills_delivered']} kills). Tested on {n_msgs:,} generated messages over real SMTP. "
         f"Keyword triage is a baseline: uncertain mail goes to a person.")
GH_DESC = ("Inbound email triage and auto-reply pipeline in Python with crash-safe sending: no duplicate replies, tested with forced process kills "
           "over real SMTP; automated mail carrying standard markers is not answered. Includes a naive baseline, generated test data and one-command reproduction.")
assert c["pipeline_targeted"]["delivery"]["duplicates"] == 0 == c["pipeline_random_wall_clock"]["delivery"]["duplicates"]
assert b["pipeline"]["replies_to_automated_senders"] == 0
assert len(TITLE) <= 40 and len(DESC) <= 500 and len(SHORT) <= 300 and len(GH_DESC) <= 350, (len(TITLE), len(DESC), len(SHORT), len(GH_DESC))

CAPTIONS = OrderedDict([
    ("01-outcome", f"{kills} forced process kills, 0 duplicate replies, 0 lost: all {replies} queued acknowledgements delivered exactly once (generated test data)."),
    ("02-in-action", "Four real messages from the generated test inbox: an order question gets a reply, an out-of-office and an unsubscribe get none, an unclear message goes to a person."),
    ("03-the-problem", f"The test inbox: {n_msgs:,} generated messages, {sum(d['categories'][k] for k in ('bulk','auto_reply','bounce'))} of them machines. A naive responder sent {nb} replies to automated senders."),
    ("04-the-approach", f"Each state change is committed and the send is committed before the SMTP call. {kp['after_smtp_before_commit']} kills landed after the server accepted a reply and before the commit; none caused a re-send."),
    ("05-the-data", f"Machine mail with standard markers: {bp['machine_mail']['correct']} of {bp['machine_mail']['n']} identified. New wording: {unseen['accuracy']*100:.1f}% correct, {unseen['manual_review']} sent to a person, {unseen['misrouted_not_review']} wrong. Open: {fc['replied']} of {fc['n']} unmarked automated messages got a reply."),
    ("06-the-proof", f"Duplicates and losses are counted from files the SMTP server received. {R['tests']['passed']} of {R['tests']['tests']} tests pass; one command reproduces everything."),
])
RATIONALE = OrderedDict([
    ("01-outcome", "Cover: leads with the strongest measured result as an oversized figure that reads at thumbnail size, on a dark ground that stands out in the grid. The labels under it are scoped to what was measured (queued replies, automated mail in the test set)."),
    ("02-in-action", "For a client who does not read code: one real order question becomes a reply (shown as the file the SMTP server received), and three real messages show what is deliberately not answered (out-of-office, unsubscribe) or handed to a person (unclear wording). Every line of text is read from the generated inbox and the delivered reply."),
    ("03-the-problem", "Shows what the inbox really contains and what a naive responder gets wrong, using the real counts as zero-based bars."),
    ("04-the-approach", "Explains the single design idea (commit before the network call, settle by the ledger) next to the real code lines it comes from."),
    ("05-the-data", "Reports triage honestly: strong on structure, weak on unseen wording, with the safe fallback (a person gets uncertain mail) made visible, and three open numbers shown on the image itself: wanted replies not sent, unmarked automated mail still answered, unsubscribe requests answered."),
    ("06-the-proof", "Shows how the claims were checked: delivery counted at the SMTP server, the test suite, and one-command reproduction."),
])

entry = f"""# Upwork portfolio entry: email automation

Upload the six images in this order (PNG recommended; JPG copies are in `images/`). Image 1 is the cover. Upwork's Project Catalog help article
describes up to 20 images and says images cannot be reordered once uploaded; your portfolio form may differ, so upload in this order and check how many
images it accepts. If it accepts fewer than six, leave out `03-the-problem` first: the in-action image already shows what is in the inbox.

## Project title ({len(TITLE)} characters)

{TITLE}

## Description ({len(DESC)} characters)

{DESC}

Shorter version ({len(SHORT)} characters), if the form asks for less:

{SHORT}

## Image captions

""" + "\n".join(f"{i}. `{k}`: {v}  ({len(v)} characters)" for i, (k, v) in enumerate(CAPTIONS.items(), 1)) + f"""

## Other fields

| Field | Suggestion |
|---|---|
| Role | Developer (solo project) |
| Project date | October 2026 |
| Skills (up to five) | Python, Automation, Email Automation, SQLite, Test Automation. Pick the closest matches from Upwork's own tag list. |
| Category | Scripts and utilities, or the closest software-development category your form offers |
| Project link | Optional. Leave blank, or paste your repository link if you want to show the code. |

Limits: Upwork's help article lists up to 70 characters for a title, 600 for a description and five skills; several third-party guides quote
tighter figures (40 and 500). The text above fits the tighter ones. If your form shows a different limit, trim from the end. Images are
4000 x 3000 px; PNGs are {min(e['png_bytes'] for e in EXP)/1e6:.2f} to {max(e['png_bytes'] for e in EXP)/1e6:.2f} MB, JPGs up to {max(e['jpg_bytes'] for e in EXP)/1e6:.2f} MB.

## Repository (GitHub)

- Name: `email-automation-triage-autoreply`
- Description ({len(GH_DESC)} characters): {GH_DESC}
- Topics: `email-automation`, `python`, `smtp`, `sqlite`, `idempotency`, `crash-recovery`, `email-triage`, `auto-reply`, `pytest`
"""
(out / "portfolio-entry-sheet.md").write_text(entry, encoding="utf-8")

by_img: dict[int, list[str]] = {}
for row in PROV:
    p = row["results_json_path"]
    by_img.setdefault(row["image"], [])
    key = p if not p.startswith(("data.", "classification.", "crash_tests.", "baseline_vs_pipeline.")) else ".".join(p.split(".")[:4])
    if key not in by_img[row["image"]]:
        by_img[row["image"]].append(key)
files_by_img: dict[int, list[str]] = {}
for row in PROV:
    if row["results_json_path"].startswith("read from file at build time: "):
        f = row["results_json_path"].split(": ", 1)[1]
        files_by_img.setdefault(row["image"], [])
        if f not in files_by_img[row["image"]]:
            files_by_img[row["image"]].append(f)


def src_line(i: int) -> str:
    keys = [p for p in by_img.get(i, []) if not p.startswith("read from")]
    files = sorted(files_by_img.get(i, []))
    parts = []
    if keys:
        parts.append("Numbers come from `results/results.json` (" + ", ".join(f"`{p}`" for p in keys) + ")")
    if files:
        parts.append(("No figures here; the" if not keys else "The") + " text is read from " + ", ".join(f"`{f}`" for f in files) + "; each outcome is checked against the triage log and the SMTP ledger when the image is built")
    if i == 4:
        parts.append("the code excerpt is read from `src/mailtriage/sender.py`")
    return "; ".join(parts) + ". Every displayed figure and excerpt is listed in `portfolio/provenance.json`."


img_names = list(CAPTIONS)
min_ratio = min(a["ratio"] for a in AUD if "passes_AA_normal" in a)  # text colours only; the grey is for graphics
notes = f"""# Delivery notes

## What was built

**Subject: email automation.** The problem chosen is the one inbound-email automations most often get wrong: an auto-responder that
double-sends after a crash, answers out-of-office replies and bounces (mail loops), or silently drops work on restart. The deliverable is a
Python pipeline that ingests RFC 5322 messages, classifies and routes them, extracts order ids / invoice numbers / amounts / bounced
addresses, and sends acknowledgements over real SMTP, with a naive baseline for comparison, a test suite, crash campaigns and a
one-command reproduction.

## What changed in this revision

- **New image 2, "in action".** A real order question, what triage decided and the reply the SMTP server received, plus three messages that are
  deliberately not answered (out-of-office, unsubscribe) or handed to a person (unclear wording). The problem, approach, data and proof images
  are now 3 to 6.
- **Numbers that were only in the results file are now shown**: of {rp['expected_replies']} wanted acknowledgements {rp['replies_delivered_unique']} were sent, {rp['missed_replies']} were not,
  {rp['extra_replies']} were sent that should not have been, {rp['extra_to_unsubscribe_requests']} of {n_unsub} unsubscribe requests got a reply. They are in the README, the entry sheet, these notes and on image 5.
- **Claims are scoped.** "No answers to bots" now says automated mail that carries a standard marker; the cover labels say "queued replies" and
  "automated mail"; the "{kills} kills" figure is described as two separately audited campaigns.
- **New measurement of machine mail the rules were not written for** (three sets, 14 formats each). It exposed a real defect: automated mail with
  no standard marker was answered. Two second-look guards, each frozen by hash before the next set was written, hold such mail for a person.
  The held-out set still leaves {fc['replied']} of {fc['n']} answered, and that is reported rather than tuned away.
- **The random-kill campaign now reliably reaches its {kr} kills** (25 ms delay; it reached 38 to 39 at 12 ms).
- **Reply wording fixed**: an order-status reply used to say "we have received your order"; it now says "your order question".
- **Image 5 headline reframed** from "Weak on new wording" to "Unsure? A human decides", with the open numbers shown on the image.
- **Tests: {R['tests']['tests']}** (was 58). The new ones cover both guards and the format sets.

## Measured results (all from `results/results.json`)

- **Delivery integrity.** Server-side audit of what a local SMTP server actually received. Pipeline: {kt} targeted kills inside the send path and
  {kr} random wall-clock kills (SIGKILL): {replies} of {replies} queued replies delivered exactly once, 0 duplicates, 0 lost in both campaigns. {kp['after_smtp_before_commit']} of the targeted kills landed after the
  server accepted a reply and before the pipeline committed it; all {kp['after_smtp_before_commit']} were settled from the server's ledger without a second send. Naive responder under {c['naive_targeted']['kills_delivered']} kills:
  {c['naive_targeted']['delivery']['duplicates']} duplicates ({c['naive_targeted']['duplicates_caused_by_crashes']} caused by the kills, the rest by re-delivered messages).
- **Machine mail with standard markers.** Naive responder: {nb} replies to automated senders, {b['naive_responder']['replies_inside_cooldown']} inside the 24 h cooldown. Pipeline: {b['pipeline']['replies_to_automated_senders']} to automated senders; {bp['machine_mail']['correct']} of {bp['machine_mail']['n']} machine messages identified.
  All {bp['machine_mail']['n']} carry a standard marker (an Auto-Submitted, Precedence or List-* header, a delivery-report structure, or a mailer-daemon / no-reply sender).
- **Reply policy, counted at the SMTP server.** {rp['expected_replies']} acknowledgements wanted, {rp['replies_delivered_unique']} sent. Not sent: {rp['missed_replies']} ({rp['missed_to_manual_review']} held for a person, {rp['missed_treated_as_unsubscribe']} treated as unsubscribe requests; {rp['missed_in_unseen_wording']} of {rp['missed_replies']} in wording the rules had never seen).
  Sent but not wanted: {rp['extra_replies']} ({rp['extra_inside_cooldown']} inside the 24 h cooldown after the same sender's earlier message went to a person, {rp['extra_to_unsubscribe_requests']} to unsubscribe requests in new wording). {rp['acknowledged_under_wrong_topic']} acknowledgements named the wrong topic.
- **Automated mail with no standard marker is the weak spot.** Three sets of 196 machine messages in 14 formats each; {fm['formats-a']['off']['groups']['unmarked']['n']} / {fm['formats-b']['off']['groups']['unmarked']['n']} / {fm['formats-c']['off']['groups']['unmarked']['n']} of them carry no marker (receipts, leave notices without headers, alerts, password mails).
  With no guard the pipeline answered {fm['formats-a']['off']['groups']['unmarked']['replied']}, {fm['formats-b']['off']['groups']['unmarked']['replied']} and {fm['formats-c']['off']['groups']['unmarked']['replied']} of them. A wording check (`guard.py`, developed on set a) and a role-address check (`roles.py`, developed on sets a and b) now hold such mail for a person.
  Set c was written after both were frozen and never tuned on: **{fc['replied']} of {fc['n']} unmarked messages are still answered** ({fm['formats-c']['wording']['groups']['unmarked']['replied']} with the wording check alone). The zeros on sets a and b are development-set results and are not a fair figure.
  The guards held {R['guard_on_main_sets']['test_held_for_review']} human messages on the main test set.
- **Triage, honestly.** On wording the rules had seen: {bp['human_seen_wording']['correct']} of {bp['human_seen_wording']['n']}. On wording they had never seen: {unseen['accuracy']*100:.1f}% correct ({unseen['correct']} of {unseen['n']}), {unseen['manual_review']} sent to manual review, {unseen['misrouted_not_review']} wrong; sales and refund recall on unseen wording is 0%.
  The blended {t['category_accuracy']*100:.1f}% is in the README but is not a fair headline. Field extraction: {t['extraction']['fields_correct']} of {t['extraction']['fields_expected']} exact.
- **Tests.** {R['tests']['passed']} of {R['tests']['tests']} pass, including self-checks that plant a duplicate and a loss to prove the audit can fail.

## Files in the zip

| Path | What |
|---|---|
| `images/` | the six 4000 x 3000 px images, PNG and JPG |
| `portfolio-entry-sheet.md` | title, description, captions and other form fields, with character counts |
| `email-automation-triage-autoreply/` | the repository, ready to push (includes `results/`, `data/`, `portfolio/` build scripts and HTML sources) |
| `DELIVERY-NOTES.md` | this file |

## The six images

""" + "\n".join(f"""**{i}. `{k}`**: {RATIONALE[k]}
{src_line(i)}
""" for i, k in enumerate(img_names, 1)) + f"""
Every image carries a quiet caption that the data is generated.

## Verification performed

- Full pipeline, test suite and crash campaigns run in the build environment, then again in a **fresh directory** (a copy of the repository without
  `results/` or any virtualenv) with `./reproduce.sh`: new virtualenv, pinned requirements, data regenerated and compared with the committed copy.
  {FRESH['fields_compared']:,} deterministic result fields matched between the two runs (data checksums, every classification, extraction, reply-policy and format-set score, baseline numbers,
  targeted-campaign delivery and reconciliation counts, test counts). The fields left out of the comparison (timings, environment, the random campaign's reconciliation split) are
  listed in `portfolio/fresh-run-check.json`. The random wall-clock campaign varies by run: both runs landed {kr} kills with 0 duplicates and 0 lost, but the split of reconciliations
  differed ({c['pipeline_random_wall_clock']['reconciliation']['already_delivered_not_resent']} already-delivered / {c['pipeline_random_wall_clock']['reconciliation']['never_delivered_resent']} re-sent in the shipped run, {FRESH['random_campaign_fresh']['already_delivered_not_resent']} / {FRESH['random_campaign_fresh']['never_delivered_resent']} in the fresh run).
  The fresh run passed {FRESH['tests_fresh']['passed']} of {FRESH['tests_fresh']['tests']} tests.
- Test data regenerates byte-for-byte from its seed (checked on every run). The classifier, extraction and parser were frozen by hash before the unseen-wording
  phrase bank was written; `guard.py` and `roles.py` were frozen before the format set that measures them was written. All are unchanged (`data/RULES_FROZEN.sha256`, checked on every run).
- Image export checks (`portfolio/export-report.json`): all {len(EXP)} images are {EXP[0]['pixels'][0]} x {EXP[0]['pixels'][1]} px, {EXP[0]['dpi'][0]} DPI metadata, embedded sRGB profile, under 5 MB;
  zero fallback fonts (asked of the browser per text node), zero font load errors, zero clipped or overlapping text, smallest text {min(e['smallest_text_css_px'] for e in EXP):.0f} CSS px
  ({min(e['smallest_text_css_px'] for e in EXP) * 2.5:.0f} px in the export). Every text colour passes WCAG AA on its background (lowest ratio {min_ratio}).
  Each image was also inspected visually and at 400 x 300 px. On image 2, every line of message and reply text is read from the generated files and each outcome is asserted
  against the triage log and the SMTP ledger at build time, so the picture cannot drift from the data.
- Hygiene scan of the whole tree: {HYGIENE}

## Deliberate choices and limits you should know about

- **All inbound mail is generated.** Real customer mail cannot be redistributed. Results describe this generated inbox, not real-world mail.
- **I did not push to GitHub or upload to Upwork**: I have no access to your accounts. The push commands are below.
- **The naive responder is a baseline I wrote** for the comparison; real scripts vary. "{kills} kills" is the sum of two separately audited campaigns ({kt} + {kr}).
- **"Crash" means SIGKILL of the process**, not power loss, disk failure or network partitions. The local SMTP server is a test sink, not a mail provider; no IMAP, TLS, authentication or non-English mail was tested.
- **Gmail and Outlook are not built or tested.** The README's "Using it with a real mailbox" section says what would change (reading from a mailbox instead of a folder, authenticated TLS sending); none of it was run.
- **Keyword triage is weak on new wording**, and image 5 says so. The {rp['extra_inside_cooldown']} pipeline replies inside the cooldown window all follow a sender's earlier message that went to a person.
- **Automated mail with no standard marker can still get a reply** ({fc['replied']} of {fc['n']} on the held-out format set). Each sender gets at most one acknowledgement per 24 h and the replies carry `Auto-Submitted`, which bounds the damage but does not prevent it.
- **The guards were not tuned on the main test set, with one disclosed exception**: four human test messages that the first draft held were seen while fixing its false positives (README, "Honest limits").
- **Throughput is not shown on the images**: measured on a {R['meta']['cpus']}-CPU container, and it varied between runs ({R['throughput']['messages_per_second_ingest_parse']} messages/s ingest and parse here, {FRESH['fresh_environment']['ingest_parse_messages_per_second']} in the fresh run).
- The display fonts lack some symbols (arrows, check marks) in the text, so none are used there; fonts are embedded under the SIL Open Font License (texts in `portfolio/fonts/`).
- Upwork's field limits differ between its help article and third-party guides; the entry sheet fits the stricter figures. Check your form, including how many images it accepts.

## Re-export the images

```bash
pip install -r portfolio/requirements.txt && playwright install chromium
python portfolio/build_images.py && python portfolio/export_images.py
```

## Publish the repository

```bash
cd email-automation-triage-autoreply
git init -b main
git add .
git commit -m "Email triage and crash-safe auto-reply pipeline"
git remote add origin <YOUR-REPOSITORY-URL>
git push -u origin main
```

Replace `<YOUR-REPOSITORY-URL>` with the URL of an empty repository you create. `./reproduce.sh` regenerates `results/` on any machine with Python 3.10+.
"""
(out / "DELIVERY-NOTES.md").write_text(notes, encoding="utf-8")
print("title", len(TITLE), "| desc", len(DESC), "| short", len(SHORT), "| gh", len(GH_DESC), "| captions", [len(v) for v in CAPTIONS.values()])
