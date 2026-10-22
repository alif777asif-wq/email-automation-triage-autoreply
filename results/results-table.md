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
