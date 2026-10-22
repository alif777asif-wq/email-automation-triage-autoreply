# Email automation: inbound triage and crash-safe auto-reply

A small, fully tested pipeline that reads an inbox of RFC 5322 messages, decides what each one is, extracts the
fields that matter, routes it to a queue, and sends an automatic acknowledgement over real SMTP, **without
double-sending, without answering automated mail that carries standard markers, and without losing a reply when the
process is killed mid-run.**

It exists because the usual "auto-responder script" fails in three predictable ways: it answers auto-replies and
bounces (mail loops), it answers the same message twice after a crash, and it quietly drops work when it restarts.
Each of those is measured below against a deliberately naive baseline that is included in this repository.
Automated mail with *no* standard markers (a receipt, a shipping notice, a stripped leave notice) is a harder problem: it is
measured separately below, including the formats that still get an automatic reply.

## Results

<!-- RESULTS:START -->
Measured on the generated **test** set (1,200 unique messages in 1,246 files; seed 202).
Python 3.13.16, Linux 6.18.44-fc-v139 x86_64, 2 CPU. Source: `results/results.json`.

**Delivery integrity (what the SMTP server actually received)**

| Test | Forced kills (SIGKILL) | Replies delivered | Duplicates | Lost |
|---|---:|---:|---:|---:|
| Pipeline, kill points inside the send path | 60 | 681 of 681 | 0 | 0 |
| Pipeline, random wall-clock kills | 40 | 681 of 681 | 0 | 0 |
| Naive responder, same kind of kills | 54 | 1200 unique | 64 (18 caused by the kills) | 0 |

**Naive responder vs this pipeline, uninterrupted run on the same inbox**

| Metric | Naive | Pipeline |
|---|---:|---:|
| Replies sent to automated senders (auto-replies, bounces, newsletters) | 295 | 0 |
| Replies sent inside the 24 h cooldown | 59 | 11 |
| Duplicate replies (re-delivered messages) | 46 | 0 |

The pipeline's 11 replies inside the cooldown window each follow an earlier message from the same sender that was sent to manual review, so no earlier acknowledgement existed (checked against `results/outputs/test/triage.csv`).

**What the pipeline did against the labels** (the "681 of 681" above counts replies the pipeline decided to send; the labels say which replies were wanted)

| | Messages | What they were |
|---|---:|---|
| Acknowledgement wanted | 784 | |
| Acknowledgement sent | 681 | every one delivered exactly once |
| Wanted but not sent | 119 | 117 sent to manual review (a person sees them); 2 real requests treated as unsubscribe requests, so the sender went on the suppression list. All 119 are in wording the rules had never seen |
| Sent but not wanted | 16 | 11 inside the cooldown window (see above); 5 unsubscribe requests the rules did not recognise, all in unseen wording |
| Acknowledged under the wrong topic | 36 | the reply names another team or topic than the message needed |

**Machine mail the rules were not written for.** The main test builds its machine mail from a few templates the guards were written
against, so its 100% says little about mail from systems the author never saw. Three further sets (14 formats
each, 196 messages per set, every message machine mail, every sender unique) measure that. A message "with markers"
carries a standard marker (Auto-Submitted, Precedence, List-* header, DSN structure, or a mailer-daemon, postmaster, no-reply or
notifications sender). The right outcome for every message is no automatic reply. Replies sent to the messages without markers:

| Set | Role | Answered, with markers | Messages without markers | No guard | Wording guard | Wording guard + sender-role rule |
|---|---|---:|---:|---:|---:|---:|
| `formats-a` | development set of the wording guard | 0 of 126 | 70 | 39 | 0 | 0 |
| `formats-b` | held out for the wording guard; development set of the role rule | 0 of 70 | 126 | 79 | 56 | 0 |
| `formats-c` | **held out for the whole guard** | 0 of 70 | 126 | 76 | 65 | 51 |

The guards (`guard.py`, then `roles.py`) were each frozen by hash before the next set was written (`data/RULES_FROZEN.sha256`). Neither changed
the main-test numbers: they held 0 of the 1,200 test messages for review (and 0 in dev). Messages a guard holds go to manual review,
never to a reply and never silently dropped.

On the held-out set, 51 of 126 automated messages without markers still got an acknowledgement. The formats that still get through:
`refund_processed_notice` (14 of 14), `ooo_offline_personal` (9 of 14), `order_confirmation_shop` (14 of 14), `pricing_change_from_a_person` (14 of 14). Every message with a marker went unanswered (0 of 70).

| `formats-c` format | Has markers | Messages | Answered | To a person | Recognised as machine mail |
|---|---|---:|---:|---:|---:|
| `precedence_auto_reply_ooo` | yes | 14 | 0 | 0 | 14 |
| `repository_notification` | yes | 14 | 0 | 0 | 14 |
| `marketing_from_a_person_with_list_headers` | yes | 14 | 0 | 0 | 14 |
| `qmail_failure_notice` | yes | 14 | 0 | 0 | 14 |
| `calendar_reminder_noreply` | yes | 14 | 0 | 0 | 14 |
| `founder_welcome_drip` | no | 14 | 0 | 14 | 0 |
| `delivery_exception_carrier` | no | 14 | 0 | 14 | 0 |
| `refund_processed_notice` | no | 14 | 14 | 0 | 0 |
| `bank_alert` | no | 14 | 0 | 14 | 0 |
| `ooo_offline_personal` | no | 14 | 9 | 5 | 0 |
| `ooo_travelling_personal` | no | 14 | 0 | 14 | 0 |
| `appointment_reminder` | no | 14 | 0 | 14 | 0 |
| `order_confirmation_shop` | no | 14 | 14 | 0 | 0 |
| `pricing_change_from_a_person` | no | 14 | 14 | 0 | 0 |

**Triage** (rules frozen before the second phrase bank was written; about half of the human messages in the test set use that unseen wording)

| Subset | Messages | Correct | Sent to manual review | Wrong |
|---|---:|---:|---:|---:|
| Machine mail (headers and markers) | 282 | 100.0% | 0 | 0 |
| Human mail, wording the rules had seen | 475 | 100.0% | 0 | 0 |
| **Human mail, wording the rules had never seen** | 443 | **56.9%** | 146 | 45 |
| All | 1200 | 84.1% | 146 | 45 |

| Category (whole test set) | Messages | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| billing | 175 | 91.1% | 93.1% | 92.1% |
| order_status | 221 | 92.9% | 100.0% | 96.3% |
| tech_support | 239 | 99.5% | 78.2% | 87.6% |
| sales_lead | 110 | 95.2% | 53.6% | 68.6% |
| refund_request | 98 | 88.5% | 46.9% | 61.3% |
| unsubscribe | 75 | 96.2% | 68.0% | 79.7% |
| auto_reply | 102 | 100.0% | 100.0% | 100.0% |
| bounce | 58 | 100.0% | 100.0% | 100.0% |
| bulk | 122 | 100.0% | 100.0% | 100.0% |

Macro-F1 0.873. Challenge subset (326 messages with distractors, typos or header-less machine mail): 78.5%.
Field extraction (order id, invoice number, amount, bounced address): 825 of 825 exact (100.0%).
Throughput, one run: 289.0 messages/s parsed, 204.4 replies/s over local SMTP.
Tests: 72 of 72 passed.
<!-- RESULTS:END -->

## Reproduce everything with one command

```bash
./reproduce.sh
```

It creates a virtualenv, installs the pinned requirements, regenerates the data (and checks it is byte-identical to the
committed copy), runs the tests, scores the pipeline and the naive baseline, runs the crash campaigns, and writes
`results/` (`results.json`, `results-table.md`, `run.log`, test output, per-campaign JSON, the triage table and the
delivery ledger). Needs Python 3.10+ and network access only to install the pinned requirements. Takes about two minutes.

## How it works

```
 inbox/*.eml ──► ingest ──► triage ──► send ──► SMTP server
                   │           │         │
                   └───────────┴─────────┴──► SQLite state machine (one committed transaction per transition)

 RECEIVED ─► DONE                                   no reply wanted (machine mail, unsubscribe, cooldown, review)
 RECEIVED ─► QUEUED ─► SENDING ─► SENT              reply wanted
             SENDING is committed BEFORE the SMTP call; after a crash a SENDING row is settled by asking the
             sent-ledger (a stand-in for "search the Sent folder by Message-ID"): found ─► SENT, not found ─► QUEUED
```

- **Machine-mail guards first.** Delivery-status notifications, `Auto-Submitted`, `X-Autoreply`, `Precedence: bulk`,
  `List-Unsubscribe`, no-reply senders and our own address are never answered. Our own replies carry
  `Auto-Submitted: auto-replied` and a null return path (RFC 3834), so another auto-responder will not answer them either.
- **Second look at mail with no marker.** Before a reply is queued, `guard.py` scores the wording (leave notices, receipts, shipping
  and sign-in templates, notification footers) and `roles.py` checks whether the sender is a role address (`billing@`, `orders@`,
  `notify@`, `hello@`) rather than a person. Either one sends the message to manual review. These are heuristics: they reduce
  replies to unmarked automated mail, they do not remove them (measured above). `--guard off|wording|full` selects the level.
- **Triage** is a transparent keyword scorer. Anything below the confidence threshold goes to manual review and is never auto-answered.
- **Extraction** pulls order id, invoice number, amount and bounced address with canonical normalisation.
- **Idempotent stages.** Re-delivered messages (same `Message-ID`) are processed once; reply ids are derived from the inbound id,
  so a retry can never mint a second identity for the same reply.
- **Suppression list** for unsubscribes and hard bounces; **24 h per-sender cooldown** on acknowledgements.

## Layout

| Path | What it is |
|---|---|
| `src/mailtriage/` | the pipeline (`parse`, `classify`, `guard`, `roles`, `extract`, `store`, `sender`, `pipeline`), the SMTP sink, crash harness, evaluation |
| `tests/` | pytest suite: parsing, guards, extraction, state machine, reconciliation, crash campaigns, verifier self-checks |
| `data/` | generated dev and test inboxes and the three machine-mail format sets, each with ground-truth `labels.csv` and a checksum manifest |
| `results/` | everything produced by `./reproduce.sh` |
| `portfolio/` | scripts that build the portfolio images from `results/results.json` |

## Using it with a real mailbox (not built, not tested)

Only three seams touch the outside world; the crash-safety logic does not change. This is the intended design, not something that was run.

| Seam | Here | With a real mailbox |
|---|---|---|
| Ingest | reads `*.eml` files | IMAP or the Gmail / Microsoft Graph API; the provider's message id plus `Message-ID` is the dedupe key (ingest is already idempotent), and a message is marked processed only after the database commit |
| Settling an unfinished send | the SMTP sink's ledger | search the Sent folder for the reply's `Message-ID` (IMAP `SEARCH HEADER`, or `rfc822msgid:` in the Gmail API) |
| Send | plain SMTP to localhost | authenticated STARTTLS SMTP or the provider's send API, keeping the null return path and `Auto-Submitted` |

New work a real mailbox needs: OAuth or app passwords, provider rate limits and quotas, threading, attachments, non-English mail, and a single
worker per mailbox. Before switching on auto-replies for a real inbox, restrict them to a list of known customers or a dedicated support address.

## Honest limits

- **All mail is generated.** Real customer mail cannot be redistributed, so the inboxes are produced by a seeded generator
  (`src/mailtriage/datagen.py`) using reserved example domains and fictional names. Accuracy on real mail is not implied.
- **The dev score is meaningless as a headline.** Rules and dev templates were written by the same author, and the dev set scores 100%.
  The test set uses a second phrase bank written *after* the rules were frozen (hashes in `data/RULES_FROZEN.sha256`, checked on every run).
  Nothing was tuned on it. That is where the lower, honest triage number comes from.
- **Even the test score is a blend.** About half of the human messages in the test set reuse wording the rules were written for.
  The triage table separates them: on wording the rules had never seen, accuracy is far lower, and sales and refund recall collapses.
  The safe fallback (manual review, no auto-reply) limits the damage but does not remove it: some unseen-wording messages are misrouted
  and receive the wrong acknowledgement.
- **The classifier is a keyword baseline.** It is explainable and needs no training data, but it only knows the words it was written
  for. A trained model is the obvious next step; that was not built or measured here.
- **Automated mail without standard markers is only partly handled.** "0 replies to automated senders" holds for mail that carries a
  marker, which is all of the main test's machine mail. For mail that carries none, the wording guard and the sender-role rule cut the
  replies but a large share still get through on the held-out set (table above, with the formats named). Two things bound the damage
  without preventing it: each sender gets at most one acknowledgement per 24 h, and our replies carry `Auto-Submitted`.
- **The role rule has a cost that is not measured.** A genuine message from a role mailbox (a business customer writing from `accounts@`)
  is held for a person instead of being acknowledged. Every generated human sender is a personal address, so the data cannot show how
  often that happens on real mail.
- **The format sets are held out, not independent.** The same author wrote the rules and the sets, in that order, with hashes recording
  the order. An outside reviewer would find formats that were not thought of. `formats-a` and `formats-b` became development sets for
  the guards once they had been looked at; only `formats-c` is a clean measurement of the finished guard.
- **The guard's first version was too eager.** Checked against the main sets, it held two dev and four test human messages (customers
  who mentioned their "payment method" or a possible "unsubscribe"). Two patterns were tightened using the dev examples, and the guards
  now hold none. The four test messages were seen when that happened, so "nothing was tuned on the test set" is true of the classifier,
  extraction and parser, and for the guards it is true apart from this one check.
- **"Crash" means the process is killed with SIGKILL**, at instrumented points and at random instants. It does not cover power loss,
  disk corruption, or network partitions. SQLite is run with `synchronous=FULL`. The headline "100 kills" is two separately audited
  campaigns (60 targeted + 40 random). Only the targeted one deliberately kills inside the narrow window between the server accepting a
  message and the commit; few random kills land there (see `reconciliation` in `results/results.json`). The random campaign's send
  delay is 25 ms because a measurement showed that at 12 ms it reached only 38 or 39 of its 40 kills in 3 of 3 repeats, and 40 in 3 of 3 at 25 ms.
- **Exactly-once delivery is not claimed.** SMTP cannot offer it. The pipeline asks the ledger what really happened and resolves the
  ambiguity; the audit counts what the server received. A residual race exists if a server accepts a message after the sender has
  died *and* after the ledger check; it did not occur in any run here. With no ledger available, ambiguous rows go to manual review
  instead of being re-sent.
- **The SMTP server is a local test sink**, not a mail provider. No IMAP/POP/Gmail/Outlook API, TLS, authentication, non-English mail,
  concurrency or large volumes were tested. Throughput is one run on a small container (CPU count above) and varies between runs.
- **The naive responder is a baseline written for this comparison**; real scripts vary.

## Credits and licences

Code: MIT (see `LICENSE`). Dependencies: aiosmtpd (Apache-2.0), pytest (MIT). All test data is synthetic.
Portfolio fonts, embedded in `portfolio/html/`: Instrument Serif, Hanken Grotesk and IBM Plex Mono, each under the SIL Open
Font License 1.1 (texts in `portfolio/fonts/`).
