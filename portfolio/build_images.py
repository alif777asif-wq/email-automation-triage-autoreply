"""Build the six portfolio images (HTML, 1600x1200 CSS px) from results/results.json and the generated test inbox.

Every number shown on an image goes through F(), which also records where it came from (provenance.json).
The message and reply text on image 2 is read from the generated inbox and the delivered reply (read_mail), and the outcome shown for
each message is checked against triage.csv and the SMTP sink ledger. The code excerpt on image 4 is read from the real source file.
Run after `./reproduce.sh`, which writes the files this script reads.
"""
from __future__ import annotations

import base64
import csv
import html
import json
import re
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
R = json.loads((ROOT / "results" / "results.json").read_text())
FONTS = HERE / "fonts"
OUT = HERE / "html"
OUT.mkdir(exist_ok=True)
N_IMAGES = 6

# ---------------------------------------------------------------- facts + provenance
PROV: list[dict] = []
IMG = 0


def dig(path: str):
    cur = R
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def F(path: str, fmt: str = "n", shows: str = "") -> str:
    """Fetch a value from results.json, format it, and record provenance for the current image."""
    v = dig(path)
    text = {"n": lambda x: f"{x:,}", "p1": lambda x: f"{100 * x:.1f}%", "p0": lambda x: f"{100 * x:.0f}%",
            "s": str, "f3": lambda x: f"{x:.3f}"}[fmt](v)
    PROV.append({"image": IMG, "shows": shows or path, "displayed": text, "results_json_path": path})
    return text


def raw(path: str):
    return dig(path)


def E(text: str) -> str:
    return html.escape(text, quote=True)


# ---------------------------------------------------------------- design tokens + contrast audit
LIGHT = dict(bg="#F3EFE7", ink="#14171C", mute="#555A62", rule="#D3CDBF", panel="#E8E2D5", good="#0A6A5B",
             bad="#B5361A", neutral="#6D7480")
DARK = dict(bg="#12151A", ink="#F3EFE7", mute="#A5AAB1", rule="#2B3039", panel="#1A1E25", good="#55D8BA",
            bad="#FF8762", neutral="#8C93A0")


def lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


AUDIT = []
for theme, t in (("light", LIGHT), ("dark", DARK)):
    for fg in ("ink", "mute", "good", "bad"):
        for bgk in ("bg", "panel"):
            r = contrast(t[fg], t[bgk])
            AUDIT.append({"theme": theme, "text": fg, "on": bgk, "ratio": round(r, 2), "passes_AA_normal": r >= 4.5})
    AUDIT.append({"theme": theme, "text": "neutral (graphics only)", "on": "bg", "ratio": round(contrast(t["neutral"], t["bg"]), 2),
                  "passes_AA_graphics": contrast(t["neutral"], t["bg"]) >= 3})
assert all(a.get("passes_AA_normal", True) and a.get("passes_AA_graphics", True) for a in AUDIT), AUDIT


def b64(name: str) -> str:
    return base64.b64encode((FONTS / name).read_bytes()).decode()


def font_face(family, file, weight, style="normal"):
    return (f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{b64(file)}) format('woff2');"
            f"font-weight:{weight};font-style:{style};font-display:block}}")


FONT_CSS = "".join([
    font_face("Instrument Serif", "instrument-serif-latin-400-normal.woff2", 400),
    font_face("Instrument Serif", "instrument-serif-latin-400-italic.woff2", 400, "italic"),
    *[font_face("Hanken Grotesk", f"hanken-grotesk-latin-{w}-normal.woff2", w) for w in (400, 500, 600)],
    *[font_face("IBM Plex Mono", f"ibm-plex-mono-latin-{w}-normal.woff2", w) for w in (400, 500)],
])


def tokens(t):
    return ";".join(f"--{k}:{v}" for k, v in t.items())


BASE_CSS = ":root{" + tokens(LIGHT) + "}body.dark{" + tokens(DARK) + "}" + """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1600px;height:1200px;overflow:hidden;background:var(--bg)}
body{font-family:'Hanken Grotesk',Helvetica,Arial,sans-serif;font-weight:500;color:var(--ink);-webkit-font-smoothing:antialiased}
.cv{position:relative;width:1600px;height:1200px;padding:88px 104px 0;background:var(--bg)}
.serif{font-family:'Instrument Serif',Georgia,serif;font-weight:400}
.mono{font-family:'IBM Plex Mono',Menlo,monospace}
.kicker{font:500 24px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--good)}
.foot{position:absolute;left:104px;right:104px;bottom:46px;display:flex;justify-content:space-between;
 font:400 20px/1 'IBM Plex Mono',monospace;color:var(--mute);border-top:1px solid var(--rule);padding-top:22px}
.good{color:var(--good)}.bad{color:var(--bad)}.mute{color:var(--mute)}
"""


def foot(i: int, text: str) -> str:
    return f'<div class="foot"><span>{html.escape(text)}</span><span>{i} / {N_IMAGES}</span></div>'


def page(i: int, dark: bool, css: str, body: str, title: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{FONT_CSS}{BASE_CSS}{css}</style></head><body class='{'dark' if dark else ''}'>{body}</body></html>")


def write(i: int, name: str, dark: bool, css: str, body: str, title: str):
    (OUT / name).write_text(page(i, dark, css, body, title), encoding="utf-8")


T = "classification.test"
CT = "crash_tests"
ARROW = ('<svg width="100" height="24" viewBox="0 0 100 24"><path d="M0 12H88M76 2l14 10-14 10" fill="none" '
         'stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ARROW_S = ('<svg width="46" height="22" viewBox="0 0 46 22"><path d="M2 11H41M32 3l9 8-9 8" fill="none" '
           'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ARROW_DOWN = ('<svg width="22" height="30" viewBox="0 0 22 30"><path d="M11 2V25M3 17l8 9 8-9" fill="none" '
              'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')

# ================================================================= image 1: outcome
IMG = 1
kills = raw(f"{CT}.pipeline_targeted.kills_delivered") + raw(f"{CT}.pipeline_random_wall_clock.kills_delivered")
PROV.append({"image": 1, "shows": "total forced kills (targeted + random wall-clock campaigns)", "displayed": f"{kills}",
             "results_json_path": f"{CT}.pipeline_targeted.kills_delivered + {CT}.pipeline_random_wall_clock.kills_delivered"})
dup_t, dup_r = raw(f"{CT}.pipeline_targeted.delivery.duplicates"), raw(f"{CT}.pipeline_random_wall_clock.delivery.duplicates")
lost_t, lost_r = raw(f"{CT}.pipeline_targeted.delivery.lost"), raw(f"{CT}.pipeline_random_wall_clock.delivery.lost")
assert dup_t == dup_r == lost_t == lost_r == 0, "image 1 headline requires zero duplicates and zero lost in both campaigns"
assert raw("baseline_vs_pipeline.pipeline.replies_to_automated_senders") == 0
body = f"""<div class="cv">
<div class="kicker">Email automation · triage and auto-reply</div>
<div class="hero"><div class="zero serif">{F(f"{CT}.pipeline_targeted.delivery.duplicates", "n", "duplicate replies (both campaigns are 0)")}</div>
<div class="hr"><div class="h1 serif">duplicate replies</div>
<div class="sub">after <b>{kills}</b> forced kills of the running process</div>
<div class="pills"><span>{F(f"{CT}.pipeline_targeted.delivery.lost", "n", "lost replies (both campaigns are 0)")} lost</span>
<span>{F(f"{CT}.pipeline_targeted.kills_delivered", "n", "targeted kills")} targeted + {F(f"{CT}.pipeline_random_wall_clock.kills_delivered", "n", "random wall-clock kills")} random</span></div></div></div>
<div class="strip">
<div><div class="fig">{F(f"{CT}.pipeline_targeted.delivery.delivered_unique", "n", "replies delivered once")}<i>of</i>{F("baseline_vs_pipeline.pipeline.replies_delivered_total", "n", "replies expected")}</div><div class="lab">queued replies, each delivered exactly once</div></div>
<div><div class="fig">{F("tests.passed", "n", "tests passed")}<i>of</i>{F("tests.tests", "n", "tests total")}</div><div class="lab">automated tests passing</div></div>
<div><div class="fig"><span class="bad">{F("baseline_vs_pipeline.naive_responder.replies_to_automated_senders", "n", "naive replies to automated senders")}</span><i>vs</i>{F("baseline_vs_pipeline.pipeline.replies_to_automated_senders", "n", "pipeline replies to automated senders")}</div><div class="lab">replies to automated mail: naive script vs this one</div></div>
</div>
{foot(1, f"Generated test data · {F('data.test.unique_messages', 'n', 'unique test messages')} messages · local SMTP server")}</div>"""
css = """
.hero{position:absolute;left:104px;right:104px;top:150px;height:640px;display:flex;align-items:center;gap:64px}
.zero{font-size:760px;line-height:.8;color:var(--good);letter-spacing:-.02em}
.h1{font-size:136px;line-height:.95}
.sub{font-size:42px;line-height:1.25;margin-top:26px}
.sub b{color:var(--good);font-weight:600}
.pills{display:flex;gap:18px;margin-top:34px}
.pills span{font:500 32px/1 'IBM Plex Mono',monospace;padding:16px 24px;border:2px solid var(--mute);border-radius:999px}
.strip{position:absolute;left:104px;right:104px;top:826px;display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--rule)}
.strip>div{padding:36px 28px 0 0}.strip>div+div{padding-left:36px;border-left:1px solid var(--rule)}
.fig{font:600 86px/1 'Hanken Grotesk',sans-serif;letter-spacing:-.025em}.fig i{font-style:normal;font-weight:500;color:var(--mute);padding:0 14px;font-size:40px;letter-spacing:0}
.lab{font:400 24px/1.3 'IBM Plex Mono',monospace;color:var(--mute);margin-top:16px}
"""
write(1, "01-outcome.html", True, css, body, "Outcome: zero duplicate replies after forced kills")

# ================================================================= image 2: in action (real messages, real outcomes)
IMG = 2
INBOX = ROOT / "data" / "test" / "inbox"
OUTD = ROOT / "results" / "outputs" / "test"
TRI = {r["file"]: r for r in csv.DictReader((OUTD / "triage.csv").open(newline="", encoding="utf-8"))}
ANSWERED = {json.loads(ln)["in_reply_to"] for ln in (OUTD / "ledger.jsonl").read_text().splitlines() if ln.strip()}
LABELS = {r["file"]: r for r in csv.DictReader((ROOT / "data" / "test" / "labels.csv").open(newline="", encoding="utf-8"))}
CAT_LABEL = {"order_status": "order status", "tech_support": "tech support", "billing": "billing", "sales_lead": "sales lead",
             "refund_request": "refund request", "unsubscribe": "unsubscribe request", "bulk": "newsletter / bulk",
             "auto_reply": "out-of-office reply", "bounce": "bounce (DSN)", "unknown": "not sure"}


def read_mail(path: Path):
    m = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    part = m.get_body(preferencelist=("plain",))
    return m, (part.get_content() if part else "")


def paras(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # the SMTP sink stores what it received, with CRLF line ends
    return [" ".join(p.split()) for p in text.strip().split("\n\n") if p.strip()]


def shown(path: Path, what: str, text: str) -> str:
    """Record that `text` on the image was read from `path`."""
    PROV.append({"image": IMG, "shows": what, "displayed": text,
                 "results_json_path": f"read from file at build time: {path.relative_to(ROOT).as_posix()}"})
    return E(text)


def inbound(fname: str):
    path = INBOX / fname
    m, text = read_mail(path)
    return {"path": path, "msg": m, "addr": parseaddr(str(m["From"]))[1], "subject": str(m["Subject"]),
            "body": paras(text)[0], "row": TRI[fname], "label": LABELS[fname], "mid": str(m["Message-ID"])}


def mail_block(x: dict, head: str = "") -> str:
    return ((f'<div class="mh">{head}</div>' if head else "") + f'<div class="ms">{shown(x["path"], "subject line", x["subject"])}</div>'
            f'<div class="mf">{shown(x["path"], "sender address", x["addr"])}</div>'
            f'<div class="mb">{shown(x["path"], "message text", x["body"])}</div>')


# --- the order question and the reply the SMTP server really received
q = inbound("m00000.eml")
assert q["row"]["category"] == "order_status" and q["row"]["state"] == "SENT" and q["mid"] in ANSWERED
rp_path = next(p for p in sorted((OUTD / "sample-replies").glob("*.eml"))
               if str(BytesParser(policy=policy.default).parsebytes(p.read_bytes(), headersonly=True)["In-Reply-To"]) == q["mid"])
rp, rp_text = read_mail(rp_path)
rp_paras = paras(rp_text)
assert str(rp["Auto-Submitted"]) == "auto-replied" and len(rp_paras) == 4
fields = json.loads(q["row"]["fields"])
assert q["row"]["ticket"] in rp_text and fields["order_id"] in rp_text
assert str(rp["To"]) == q["addr"]
reply_card = (f'<div class="mh good">Reply delivered</div><div class="ms">{shown(rp_path, "reply subject", str(rp["Subject"]))}</div>'
              + "".join(f'<div class="mb">{shown(rp_path, "reply text", p)}</div>' for p in rp_paras))
decision = (f'<div class="mh">Triage decides</div><div class="cat">{E(CAT_LABEL[q["row"]["category"]])}</div>'
            f'<div class="kv"><span>queue</span>{shown(TRI_PATH := OUTD / "triage.csv", "queue", q["row"]["queue"])}</div>'
            f'<div class="kv"><span>order</span>{shown(TRI_PATH, "order id found in the text", fields["order_id"])}</div>'
            f'<div class="kv"><span>ticket</span>{shown(TRI_PATH, "ticket number", q["row"]["ticket"])}</div>')

# --- three messages that do not get an acknowledgement, and why
CASES = [("m00030.eml", "auto_reply", "No reply", "good", "A machine never gets an answer."),
         ("m00062.eml", "unsubscribe", "No reply", "good", "Sender goes on the suppression list."),
         ("m00028.eml", "unknown", "A person decides", "neutral", "A sales enquiry in new wording.")]
minis = ""
for fname, expect, verdict, tone, why in CASES:
    x = inbound(fname)
    assert x["row"]["category"] == expect and x["mid"] not in ANSWERED, (fname, x["row"])
    if expect == "unknown":
        assert x["label"]["category"] == "sales_lead", x["label"]  # the plain-words note under the card is true
    minis += (f'<div class="mini"><div class="mail">{mail_block(x)}</div><div class="dn">{ARROW_DOWN}</div>'
              f'<div class="dec t-{tone}"><div class="vd">{E(verdict)}</div><div class="why">{E(why)}</div>'
              f'<div class="rs">triage: {E(CAT_LABEL[expect])}</div></div></div>')
body = f"""<div class="cv">
<div class="kicker">In action · four real messages</div>
<div class="h2 serif">What happens to each message.</div>
<div class="sub2">Text copied from the generated test inbox and from the reply the SMTP server received.</div>
<div class="top"><div class="mail q">{mail_block(q, "Arrives")}</div><div class="ar">{ARROW_S}</div><div class="decc">{decision}</div><div class="ar">{ARROW_S}</div><div class="mail">{reply_card}</div></div>
<div class="three">{minis}</div>
{foot(2, "Generated test data · text from data/test/inbox and the delivered reply")}</div>"""
css = """
.h2{font-size:80px;line-height:1.0;margin-top:24px;white-space:nowrap}
.sub2{font-size:28px;line-height:1.3;margin-top:14px;max-width:1392px}
.top{display:grid;grid-template-columns:500px 58px 268px 58px 508px;margin-top:24px;align-items:center}
.mail{background:var(--panel);border:1px solid var(--rule);border-radius:14px;padding:20px 24px;align-self:stretch}
.mh{font:500 19px/1.2 'IBM Plex Mono',monospace;color:var(--mute);letter-spacing:.08em;text-transform:uppercase}
.mh.good{color:var(--good)}
.ms{font:600 26px/1.2 'Hanken Grotesk',sans-serif;margin-top:10px}
.mf{font:400 20px/1.3 'IBM Plex Mono',monospace;color:var(--mute);margin-top:6px;overflow-wrap:anywhere}
.mb{font:400 22px/1.36 'Hanken Grotesk',sans-serif;margin-top:8px}
.mail.q{align-self:center}
.ar{display:flex;justify-content:center;color:var(--mute)}
.decc{padding:0 0 0 2px}
.cat{font:600 34px/1.15 'Hanken Grotesk',sans-serif;margin-top:10px;color:var(--good)}
.kv{font:500 21px/1.3 'IBM Plex Mono',monospace;margin-top:8px;overflow-wrap:anywhere}
.kv span{display:block;font:400 19px/1.2 'IBM Plex Mono',monospace;color:var(--mute);text-transform:uppercase;letter-spacing:.08em}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;margin-top:20px}
.mini{display:flex;flex-direction:column}
.mini .mail{flex:1}
.dn{display:flex;justify-content:center;color:var(--mute);margin:6px 0 4px}
.dec{border-left:6px solid var(--good);padding:2px 0 2px 16px;min-height:106px}
.dec.t-neutral{border-left-color:var(--neutral)}
.vd{font:600 28px/1.15 'Hanken Grotesk',sans-serif}
.why{font:500 22px/1.3 'Hanken Grotesk',sans-serif;margin-top:6px}
.rs{font:400 19px/1.3 'IBM Plex Mono',monospace;color:var(--mute);margin-top:8px}
"""
write(2, "02-in-action.html", False, css, body, "In action: four real messages and what happened to each")

# ================================================================= image 3: the task
IMG = 3
cats = R["data"]["test"]["categories"]
human = ["order_status", "tech_support", "billing", "sales_lead", "refund_request", "unsubscribe"]
machine = ["bulk", "auto_reply", "bounce"]
label = {"order_status": "order status", "tech_support": "tech support", "billing": "billing", "sales_lead": "sales lead",
         "refund_request": "refund request", "unsubscribe": "unsubscribe", "bulk": "newsletter / bulk",
         "auto_reply": "out-of-office", "bounce": "bounce (DSN)"}
mx = max(cats.values())
machines_total = sum(cats[c] for c in machine)
PROV.append({"image": 3, "shows": "machine messages (bulk + auto_reply + bounce)", "displayed": f"{machines_total:,}",
             "results_json_path": "data.test.categories.{bulk,auto_reply,bounce} summed"})


def bar(c, cls):
    v = cats[c]
    PROV.append({"image": IMG, "shows": f"messages in category {c}", "displayed": f"{v}", "results_json_path": f"data.test.categories.{c}"})
    return (f'<div class="row"><span class="nm">{label[c]}</span><span class="trk"><span class="bf {cls}" '
            f'style="width:{v / mx * 100:.2f}%"></span></span><span class="ct">{v:,}</span></div>')


bars = "".join(bar(c, "h") for c in human) + '<div class="gap"></div>' + "".join(bar(c, "m") for c in machine)
body = f"""<div class="cv">
<div class="kicker">The problem</div>
<div class="h2 serif">Nearly a quarter is machines.</div>
<div class="sub2">{machines_total} of {F("data.test.unique_messages", "n", "unique test messages")} messages are out-of-office replies, bounces or newsletters, and none should get an answer.
A naive responder sent <b>{F("baseline_vs_pipeline.naive_responder.replies_to_automated_senders", "n", "naive replies to automated senders")}</b> replies to automated senders.</div>
<div class="cols"><div class="chart">{bars}
<div class="legend"><span><i class="sw h"></i>human, answer once</span><span><i class="sw m"></i>machine, never answer</span></div></div>
<div class="facts">
<div class="fact"><div class="fn serif">{F("data.test.redelivered_copies", "n", "re-delivered copies in the inbox")}</div><div class="fl">messages arrive twice, same Message-ID</div></div>
<div class="fact"><div class="fn serif bad">{F("baseline_vs_pipeline.naive_responder.replies_inside_cooldown", "n", "naive replies inside 24h cooldown")}</div><div class="fl">naive replies to repeat senders within 24 h</div></div>
<div class="fact"><div class="fn serif bad">{F("baseline_vs_pipeline.naive_responder.replies_to_unsubscribe_requests", "n", "naive replies to unsubscribe requests")}</div><div class="fl">naive replies to people asking to unsubscribe</div></div>
</div></div>
{foot(3, "Generated test data · seeded · reserved example domains")}</div>"""
css = """
.h2{font-size:104px;line-height:1.0;margin-top:34px;white-space:nowrap}
.sub2{font-size:33px;line-height:1.3;margin-top:26px;max-width:1392px;color:var(--ink)}
.sub2 b{color:var(--bad);font-weight:600}
.cols{display:grid;grid-template-columns:860px 1fr;gap:64px;margin-top:40px}
.row{display:grid;grid-template-columns:262px 1fr 76px;align-items:center;height:56px}
.nm{font:500 24px/1 'IBM Plex Mono',monospace}.ct{font:600 27px/1 'IBM Plex Mono',monospace;text-align:right}
.trk{height:30px;background:var(--panel);display:block;border-radius:3px;margin-right:18px}
.bf{display:block;height:100%;border-radius:3px}.bf.h{background:var(--ink)}.bf.m{background:var(--bad)}
.gap{height:20px}
.legend{display:flex;gap:34px;margin-top:20px;font:400 21px/1 'IBM Plex Mono',monospace;color:var(--mute)}
.sw{display:inline-block;width:20px;height:20px;border-radius:3px;margin-right:10px;vertical-align:-3px}
.sw.h{background:var(--ink)}.sw.m{background:var(--bad)}
.facts{border-left:1px solid var(--rule);padding-left:44px;display:flex;flex-direction:column;justify-content:space-between;height:538px}
.fn{font-size:92px;line-height:1}.fl{font:400 22px/1.35 'IBM Plex Mono',monospace;color:var(--mute);margin-top:8px;max-width:380px}
"""
write(3, "03-the-problem.html", False, css, body, "The problem: machine mail and duplicates")

# ================================================================= image 4: approach (real code excerpt)
IMG = 4
src = (ROOT / "src" / "mailtriage" / "sender.py").read_text().splitlines()


def line(anchor: str, strip_comment=False) -> str:
    hit = next(l for l in src if anchor in l)
    hit = hit.strip()
    if strip_comment:
        hit = re.sub(r"\s+#.*$", "", hit)
    return hit


code_lines = [(line('transition(mid, "SENDING"'), ""), (line('crashpoint("before_smtp")'), "1"),
              (line("conn.send_message", True), ""), (line('crashpoint("after_smtp_before_commit")'), "2"),
              (line('transition(mid, "SENT", "SENDING")'), ""), (line('crashpoint("after_sent_commit")'), "3")]
PROV.append({"image": 4, "shows": "code excerpt (6 lines)", "displayed": "src/mailtriage/sender.py", "results_json_path": "read from source file at build time"})
code_html = "".join(f'<div class="cl"><span class="cc">{html.escape(t)}</span>' + (f'<b class="kb">{n}</b>' if n else "") + "</div>"
                    for t, n in code_lines)
kp = "crash_tests.pipeline_targeted.kills_by_point"
k1, k2, k3 = (F(f"{kp}.{p}", "n", f"kills at {p}") for p in ("before_smtp", "after_smtp_before_commit", "after_sent_commit"))
rec = "crash_tests.pipeline_targeted.reconciliation"
boxes = "".join(f'<div class="st{" hot" if s == "SENDING" else ""}">{s}</div>' + (f'<div class="ar">{ARROW}</div>' if s != "SENT" else "")
                for s in ("RECEIVED", "QUEUED", "SENDING", "SENT"))
body = f"""<div class="cv">
<div class="kicker">The approach</div>
<div class="h2 serif">Kill it anywhere.<br>It resumes correctly.</div>
<div class="sub2">Every state change is one committed transaction, and the send is committed <i>before</i> the network call.
After a crash, an unfinished send is settled by asking the server&rsquo;s ledger.</div>
<div class="flow">{boxes}</div>
<div class="wins">
<div class="w"><b class="kb">1</b><div class="wt">Killed before SMTP</div><div class="wd">never left, so it is re-sent once. Killed here <span class="mono">{k1}</span> times; {F(f"{rec}.never_delivered_resent", "n", "re-sent after reconcile")} re-sent.</div></div>
<div class="w"><b class="kb">2</b><div class="wt">Killed after SMTP, before commit</div><div class="wd">already delivered, so it is marked SENT and not re-sent. Killed here <span class="mono">{k2}</span> times; {F(f"{rec}.already_delivered_not_resent", "n", "settled without resend")} settled.</div></div>
<div class="w"><b class="kb">3</b><div class="wt">Killed after commit</div><div class="wd">nothing to recover. Killed here <span class="mono">{k3}</span> times.</div></div>
</div>
<div class="code">{code_html}</div>
{foot(4, "Generated test data · excerpt from src/mailtriage/sender.py")}</div>"""
css = """
.h2{font-size:96px;line-height:1.0;margin-top:30px}
.sub2{font-size:30px;line-height:1.3;margin-top:22px;max-width:1260px}
.flow{display:flex;align-items:center;margin-top:34px;color:var(--mute)}
.st{font:500 30px/1 'IBM Plex Mono',monospace;color:var(--ink);border:2px solid var(--ink);border-radius:10px;width:262px;height:92px;
 display:flex;align-items:center;justify-content:center}
.st.hot{background:var(--ink);color:var(--bg)}.ar{width:114px;display:flex;justify-content:center}
.wins{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:30px}
.w{border-top:3px solid var(--good);padding-top:18px}
.kb{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:var(--good);color:var(--bg);font:600 24px/1 'IBM Plex Mono',monospace}
.wt{font:600 27px/1.2 'Hanken Grotesk',sans-serif;margin-top:12px}
.wd{font:400 22px/1.4 'IBM Plex Mono',monospace;color:var(--mute);margin-top:10px}
.wd .mono{color:var(--ink);font-weight:500}
.code{position:absolute;left:104px;right:104px;top:862px;height:204px;background:#12151A;border-radius:14px;padding:22px 30px;display:flex;flex-direction:column;justify-content:space-between}
.cl{display:flex;justify-content:space-between;align-items:center}
.cc{font:400 21px/1 'IBM Plex Mono',monospace;color:#F3EFE7;white-space:nowrap}
.code .kb{background:#55D8BA;color:#12151A;width:30px;height:30px;font-size:19px}
"""
write(4, "04-the-approach.html", False, css, body, "The approach: committed state machine and reconciliation")

# ================================================================= image 5: data / honest accuracy
IMG = 5
U = f"{T}.by_phrasing.human_unseen_wording"
n_u, ok_u, rev_u, mis_u = (raw(f"{U}.{k}") for k in ("n", "correct", "manual_review", "misrouted_not_review"))
assert ok_u + rev_u + mis_u == n_u
pcts = [100 * ok_u / n_u, 100 * rev_u / n_u, 100 * mis_u / n_u]
for k, shows in (("n", "human messages in wording the rules had never seen"), ("correct", "correct"),
                 ("manual_review", "sent to a human"), ("misrouted_not_review", "wrong")):
    F(f"{U}.{k}", "n", shows)
order = ["order_status", "billing", "tech_support", "unsubscribe", "sales_lead", "refund_request"]
RC = f"{T}.by_phrasing.human_unseen_wording_recall"


def pc(c):
    return (f'<div class="row"><span class="nm">{label[c]} <em>n={F(f"{RC}.{c}.n", "n", f"unseen-wording messages, {c}")}</em></span><span class="trk"><span class="bf" style="width:{raw(f"{RC}.{c}.recall") * 100:.2f}%"></span></span>'
            f'<span class="ct">{F(f"{RC}.{c}.recall", "p0", f"recall on unseen wording, {c}")}</span></div>')


MM = f"{T}.by_phrasing.machine_mail"
RP = f"{T}.reply_policy"
UM = "machine_mail_formats.formats-c.full.groups.unmarked"
assert raw(f"{RP}.replies_to_automated_senders") == 0 and raw(f"{RP}.missed_replies") == raw(f"{RP}.expected_replies") - raw(f"{RP}.replies_delivered_unique") + raw(f"{RP}.extra_replies")
body = f"""<div class="cv">
<div class="kicker">The data · wording the rules had never seen</div>
<div class="h2 serif">Strong on structure.<br>Unsure? A human decides.</div>
<div class="sub2">Rules caught every machine message that carries a standard marker. On new wording, mail the rules are unsure about goes to a person, not a guess.</div>
<div class="stack"><span style="width:{pcts[0]:.3f}%;background:var(--good)"></span><span style="width:{pcts[1]:.3f}%;background:var(--neutral)"></span><span style="width:{pcts[2]:.3f}%;background:var(--bad)"></span></div>
<div class="leg"><span><i style="background:var(--good)"></i><b>{ok_u}</b> correct</span><span><i style="background:var(--neutral)"></i><b>{rev_u}</b> sent to a human</span><span><i style="background:var(--bad)"></i><b>{mis_u}</b> wrong</span><span class="mute">of {n_u} human messages</span></div>
<div class="cols4"><div class="big"><div class="bn serif">{F(f"{U}.accuracy", "p1", "accuracy on human mail in unseen wording")}</div><div class="bl">routed correctly on new wording</div>
<div class="sm"><div><b>{F(f"{MM}.correct", "n", "machine messages identified")} of {F(f"{MM}.n", "n", "machine messages")}</b><span>machine messages with standard markers found</span></div>
<div><b>{F(f"{T}.extraction.fields_correct", "n", "fields extracted exactly")} of {F(f"{T}.extraction.fields_expected", "n", "fields expected")}</b><span>ids, amounts and addresses extracted exactly</span></div></div></div>
<div class="rt"><div class="chart"><div class="ct2">Recall on unseen wording</div>{"".join(pc(c) for c in order)}</div>
<div class="open">
<div><b>{F(f"{RP}.missed_replies", "n", "acknowledgements wanted but not sent")} of {F(f"{RP}.expected_replies", "n", "acknowledgements wanted")}</b><span>wanted replies not sent; {F(f"{RP}.missed_to_manual_review", "n", "of those, held for a person")} were held for a person</span></div>
<div><b class="bad">{F(f"{UM}.replied", "n", "unmarked automated messages that got a reply")} of {F(f"{UM}.n", "n", "unmarked automated messages, new formats")}</b><span>automated messages with no standard marker still answered (new formats)</span></div>
<div><b class="bad">{F(f"{RP}.extra_to_unsubscribe_requests", "n", "unsubscribe requests that got a reply")} of {F("data.test.categories.unsubscribe", "n", "unsubscribe requests")}</b><span>unsubscribe requests got a reply, all in new wording</span></div>
</div></div></div>
{foot(5, "Generated test data · rules frozen before this wording was written")}</div>"""
css = """
.h2{font-size:84px;line-height:1.0;margin-top:28px}
.sub2{font-size:28px;line-height:1.3;margin-top:18px;max-width:1392px}
.stack{display:flex;height:50px;margin-top:26px;border-radius:6px;overflow:hidden;gap:4px}
.stack span{display:block;height:100%}
.leg{display:flex;gap:38px;margin-top:14px;font:400 23px/1 'IBM Plex Mono',monospace;color:var(--ink);align-items:center}
.leg b{font-weight:600;font-size:27px}.leg i{display:inline-block;width:20px;height:20px;border-radius:4px;margin-right:12px;vertical-align:-3px}
.cols4{display:grid;grid-template-columns:480px 1fr;gap:52px;margin-top:28px}
.big{border-right:1px solid var(--rule);padding-right:32px}
.bn{font-size:176px;line-height:.9;color:var(--good)}.bl{font:400 22px/1.35 'IBM Plex Mono',monospace;color:var(--mute);margin-top:10px}
.sm{margin-top:26px;display:flex;flex-direction:column;gap:20px}.sm b{font:600 44px/1 'Hanken Grotesk',sans-serif;display:block;letter-spacing:-.02em}
.sm span{display:block;font:400 21px/1.35 'IBM Plex Mono',monospace;color:var(--mute);margin-top:6px}
.ct2{font:500 22px/1 'IBM Plex Mono',monospace;color:var(--mute);margin-bottom:10px;letter-spacing:.08em;text-transform:uppercase}
.row{display:grid;grid-template-columns:318px 1fr 84px;align-items:center;height:46px}
.nm{font:500 23px/1 'IBM Plex Mono',monospace;white-space:nowrap}.nm em{font-style:normal;color:var(--mute);font-size:20px}
.ct{font:600 25px/1 'IBM Plex Mono',monospace;text-align:right}
.trk{height:24px;background:var(--panel);display:block;border-radius:3px;margin-right:16px}
.bf{display:block;height:100%;border-radius:3px;background:var(--good)}
.open{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;margin-top:22px;border-top:1px solid var(--rule);padding-top:20px}
.open b{font:600 42px/1 'Hanken Grotesk',sans-serif;display:block;letter-spacing:-.02em}
.open span{display:block;font:400 21px/1.35 'IBM Plex Mono',monospace;color:var(--mute);margin-top:8px}
"""
write(5, "05-the-data.html", False, css, body, "The data: held-out triage results")

# ================================================================= image 6: proof
IMG = 6
rows = []
for name, key in (("This pipeline · send-path kills", "pipeline_targeted"),
                  ("This pipeline · random kills", "pipeline_random_wall_clock"),
                  ("Naive responder · send-path kills", "naive_targeted")):
    p = f"{CT}.{key}"
    dup = F(f"{p}.delivery.duplicates", "n", f"duplicates, {key}")
    rows.append(f'<tr><td class="who">{name}</td><td>{F(f"{p}.kills_delivered", "n", f"kills, {key}")}</td>'
                f'<td>{F(f"{p}.delivery.delivered_total", "n", f"replies delivered in total, {key}")}</td>'
                f'<td class="{"bad" if dup != "0" else "good"}">{dup}</td>'
                f'<td class="{"good"}">{F(f"{p}.delivery.lost", "n", f"lost, {key}")}</td></tr>')
assert R["data"]["test"]["regenerated_byte_identical_to_committed"], "data must regenerate byte-identically"
m = R["meta"]
body = f"""<div class="cv">
<div class="kicker">The proof</div>
<div class="h2 serif">Counted at the receiving end.</div>
<div class="sub2">Duplicates and losses are found by reading the files the SMTP server actually received, not by trusting the pipeline&rsquo;s own log.</div>
<table><thead><tr><th></th><th>Kills</th><th>Replies received</th><th>Duplicates</th><th>Lost</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<div class="note">The naive responder also answers machine mail, so its total is larger.</div>
<div class="two"><div class="box"><div class="bn2 serif">{F("tests.passed", "n", "tests passed")} of {F("tests.tests", "n", "tests total")}</div><div class="bt">tests pass, including one that plants a duplicate and a loss to prove the audit can fail</div></div>
<div class="box"><div class="cmd mono">./reproduce.sh</div><div class="bt">one command regenerates the data byte-for-byte and reruns every test, score and crash campaign</div></div></div>
<div class="env">Python {F("meta.python", "s", "python version")} · {F("meta.cpus", "n", "cpus")} CPU · SQLite {F("meta.sqlite", "s", "sqlite version")} · aiosmtpd {F("meta.aiosmtpd", "s", "aiosmtpd version")} · data manifest sha256 {R["data"]["test"]["manifest_sha256"][:12]}</div>
{foot(6, "Generated test data · results/results.json")}</div>"""
PROV.append({"image": 6, "shows": "dataset checksum prefix", "displayed": R["data"]["test"]["manifest_sha256"][:12], "results_json_path": "data.test.manifest_sha256"})
css = """
.h2{font-size:100px;line-height:1.0;margin-top:30px;white-space:nowrap}
.sub2{font-size:30px;line-height:1.3;margin-top:20px;max-width:1240px}
table{width:100%;border-collapse:collapse;margin-top:40px}
th{font:500 21px/1 'IBM Plex Mono',monospace;color:var(--mute);text-align:right;padding:0 0 16px;letter-spacing:.08em;text-transform:uppercase}
th:first-child{text-align:left}
td{font:600 38px/1 'IBM Plex Mono',monospace;text-align:right;padding:22px 0;border-top:1px solid var(--rule)}
td.who{font:500 27px/1.2 'IBM Plex Mono',monospace;text-align:left;width:620px;white-space:nowrap}
.two{display:grid;grid-template-columns:1fr 1fr;gap:36px;margin-top:26px}
.note{font:400 21px/1.3 'IBM Plex Mono',monospace;color:var(--mute);margin-top:18px}
.box{background:var(--panel);border-radius:12px;padding:28px 32px;height:250px}
.bn2{font-size:88px;line-height:1;color:var(--good)}.cmd{font-size:50px;line-height:1.2;font-weight:500;color:var(--good);padding-top:14px}
.bt{font:400 22px/1.4 'IBM Plex Mono',monospace;color:var(--mute);margin-top:14px}
.env{font:400 21px/1.3 'IBM Plex Mono',monospace;color:var(--mute);margin-top:22px}
"""
write(6, "06-the-proof.html", True, css, body, "The proof: delivery audit and reproducibility")

# stale pages from an earlier numbering must not be exported
for old in OUT.glob("*.html"):
    if old.name not in {"01-outcome.html", "02-in-action.html", "03-the-problem.html", "04-the-approach.html", "05-the-data.html",
                        "06-the-proof.html"}:
        old.unlink()
(HERE / "provenance.json").write_text(json.dumps(PROV, indent=1))
(HERE / "contrast-audit.json").write_text(json.dumps(AUDIT, indent=1))
print(f"built {len(list(OUT.glob('*.html')))} pages, {len(PROV)} provenance rows")
