"""Seeded generator for synthetic inbound-email test data.

Every address uses an RFC 2606 reserved domain (example.com / .org / .net / .example)
and every name is fictional. Output per data set:
    inbox/*.eml   one RFC 5322 message per file (some are re-deliveries of the same message)
    labels.csv    ground truth: category, expected action, expected extracted fields
    MANIFEST.sha256   checksum of every file, so a re-generation can be verified byte-for-byte
"""
from __future__ import annotations

import csv
import hashlib
import html
import random
from datetime import datetime, timedelta, timezone
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from .phrases import DISTRACTORS, POOL_A, POOL_B

OWN = "support@shop.example"
DOMAINS = ["example.com", "example.org", "example.net"]
FIRST = [("Ava", "ava"), ("Noah", "noah"), ("Zoë", "zoe"), ("Mateo", "mateo"), ("Anaïs", "anais"), ("Liam", "liam"),
         ("Søren", "soren"), ("Priya", "priya"), ("Kenji", "kenji"), ("Amara", "amara"), ("Lucas", "lucas"),
         ("Fatima", "fatima"), ("Elena", "elena"), ("Tomás", "tomas"), ("Hana", "hana"), ("Oskar", "oskar"),
         ("Ines", "ines"), ("Rohan", "rohan"), ("Mei", "mei"), ("Daniel", "daniel"), ("Sofia", "sofia"),
         ("Jonas", "jonas"), ("Nadia", "nadia"), ("Ethan", "ethan"), ("Leila", "leila"), ("Marek", "marek"),
         ("Isla", "isla"), ("Hugo", "hugo"), ("Yara", "yara"), ("Felix", "felix"), ("Chloé", "chloe"),
         ("Arjun", "arjun"), ("Greta", "greta"), ("Omar", "omar"), ("Alice", "alice"), ("Viktor", "viktor"),
         ("Rina", "rina"), ("Diego", "diego"), ("Nora", "nora"), ("Kofi", "kofi")]
LAST = [("Müller", "mueller"), ("Okafor", "okafor"), ("Alvarez", "alvarez"), ("Nielsen", "nielsen"),
        ("Dupont", "dupont"), ("Tanaka", "tanaka"), ("Rossi", "rossi"), ("Haddad", "haddad"),
        ("Kowalski", "kowalski"), ("Silva", "silva"), ("Novak", "novak"), ("Larsen", "larsen"),
        ("Bianchi", "bianchi"), ("Chen", "chen"), ("Patel", "patel"), ("Johansson", "johansson"),
        ("Moreau", "moreau"), ("Schmidt", "schmidt"), ("Kim", "kim"), ("Costa", "costa"), ("Ivanov", "ivanov"),
        ("Santos", "santos"), ("Walker", "walker"), ("Mensah", "mensah"), ("Hughes", "hughes"),
        ("Lindqvist", "lindqvist"), ("Fischer", "fischer"), ("Ahmed", "ahmed"), ("Cruz", "cruz"),
        ("Berg", "berg"), ("Yilmaz", "yilmaz"), ("Murphy", "murphy"), ("Sato", "sato"), ("Petrov", "petrov"),
        ("Ricci", "ricci"), ("Lopez", "lopez"), ("Khan", "khan"), ("Evans", "evans"), ("Duarte", "duarte"),
        ("Varga", "varga")]
COMPANIES = ["Birchwood Studio", "Larkspur Foods", "Tidewater Labs", "Copperline Supply", "Quill & Anchor",
             "Northfield Clinic", "Marrow Design", "Kestrel Logistics"]
NEWSLETTERS = [("Weekly Digest", "news@newsletters.example.net"), ("Product Updates", "updates@mailer.example.org"),
               ("Deal Alerts", "deals@promo.example.com")]
BROWSERS = ["Firefox 128", "Chrome 126", "Safari 17", "Edge 126"]

HUMAN = ["billing", "order_status", "tech_support", "sales_lead", "refund_request", "unsubscribe"]
REPLY_CATS = {"billing", "order_status", "tech_support", "sales_lead", "refund_request"}
MACHINE = {"auto_reply", "bounce", "bulk"}
QUEUE = {"billing": "billing", "refund_request": "billing", "order_status": "fulfilment", "tech_support": "support",
         "sales_lead": "sales", "unsubscribe": "suppression", "bounce": "suppression", "auto_reply": "none",
         "bulk": "none"}
WEIGHTS = {"billing": 15, "order_status": 17, "tech_support": 17, "sales_lead": 10, "refund_request": 9,
           "unsubscribe": 6, "auto_reply": 9, "bounce": 5, "bulk": 9}
LABEL_FIELDS = ["file", "message_id", "category", "challenge", "is_duplicate", "duplicate_of", "expect_reply",
                "expect_reason", "queue", "order_id", "invoice_no", "amount", "bounced_address", "phrasing"]

DEV = dict(name="dev", n=400, seed=101, holdout_share=0.0)
TEST = dict(name="test", n=1200, seed=202, holdout_share=0.5)


def _typos(rng: random.Random, text: str) -> str:
    words = text.split(" ")
    for i, w in enumerate(words):
        if len(w) >= 5 and w.isalpha() and rng.random() < 0.12:
            j = rng.randrange(1, len(w) - 2)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def _html(text: str, newsletter: bool = False) -> str:
    paras = "".join(f'<p style="margin:0 0 12px">{html.escape(p).replace(chr(10), "<br>")}</p>'
                    for p in text.split("\n\n"))
    return (f"<html><head><title>m</title><style>body{{font-family:Arial,sans-serif}}</style></head>"
            f"<body>{paras}</body></html>")


def _pick_pool(rng: random.Random, holdout_share: float, category: str):
    draw = rng.random()  # always consume one draw so dev data does not depend on POOL_B contents
    use_b = bool(POOL_B.get(category)) and draw < holdout_share
    return (POOL_B[category], "B") if use_b else (POOL_A[category], "A")


def _ids(rng: random.Random, t: datetime):
    order = rng.randint(10000, 99999)
    inv_year, inv_seq = 2026, rng.randint(1, 9999)
    a = round(rng.uniform(9, 4800), 2)
    ord_disp = rng.choice([f"ORD-{order}", f"ORD{order}", f"#{order}"])
    inv_disp = rng.choice([f"INV-{inv_year}-{inv_seq:04d}", f"INV {inv_year}-{inv_seq:04d}",
                           f"INV{inv_year}-{inv_seq:04d}"])
    amt_disp = f"{a:,.2f}" if rng.random() < 0.5 else f"{a:.2f}"
    return {"ord": ord_disp, "inv": inv_disp, "amt": amt_disp, "n": rng.choice([8, 12, 25, 40, 50, 120]),
            "ver": f"{rng.randint(3, 5)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}", "browser": rng.choice(BROWSERS),
            "date": (t + timedelta(days=rng.randint(3, 14))).strftime("%d %B %Y"),
            "_order": f"ORD-{order}", "_inv": f"INV-{inv_year}-{inv_seq:04d}", "_amt": f"{a:.2f}"}


def _fill(tpl: str, ids: dict, usd: bool) -> str:
    if usd:
        tpl = tpl.replace("${amt}", "USD {amt}")
    return tpl.format(**{k: v for k, v in ids.items() if not k.startswith("_")})


def _address(person) -> tuple[str, Address]:
    (f, fa), (l, la), dom = person
    addr = f"{fa}.{la}@{dom}"
    return addr, Address(display_name=f"{f} {l}", addr_spec=addr)


def _bounce(rng, t, bounced: str, legacy: bool, mid: str) -> bytes:
    boundary = f"=_{rng.getrandbits(48):012x}"
    date = format_datetime(t)
    if legacy:
        frm = rng.choice(["Mail Delivery Subsystem <mailer-daemon@mx.example.net>",
                          "Delivery Status Notification <notifications@bounce.example.org>"])
        body = ("Delivery to the following recipient failed permanently:\n\n"
                f"     {bounced}\n\nTechnical details of permanent failure:\n"
                "DNS Error: Domain name not found\n")
        return (f"From: {frm}\nTo: {OWN}\nSubject: Delivery Status Notification (Failure)\nDate: {date}\n"
                f"Message-ID: {mid}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n{body}").encode()
    auto = "Auto-Submitted: auto-replied\n" if rng.random() < 0.5 else ""
    return (f"From: Mail Delivery System <MAILER-DAEMON@mx.example.net>\nTo: {OWN}\n"
            f"Subject: Undelivered Mail Returned to Sender\nDate: {date}\nMessage-ID: {mid}\nReturn-Path: <>\n{auto}"
            f"MIME-Version: 1.0\nContent-Type: multipart/report; report-type=delivery-status; "
            f'boundary="{boundary}"\n\n--{boundary}\nContent-Description: Notification\n'
            "Content-Type: text/plain; charset=utf-8\n\nThis is the mail system at host mx.example.net.\n\n"
            "I'm sorry to have to inform you that your message could not\nbe delivered to one or more recipients.\n\n"
            f"<{bounced}>: host mx.example.org[192.0.2.25] said: 550 5.1.1 User unknown\n\n"
            f"--{boundary}\nContent-Description: Delivery report\nContent-Type: message/delivery-status\n\n"
            f"Reporting-MTA: dns; mx.example.net\nArrival-Date: {date}\n\n"
            f"Final-Recipient: rfc822; {bounced}\nAction: failed\nStatus: 5.1.1\n"
            f"Diagnostic-Code: smtp; 550 5.1.1 User unknown\n\n--{boundary}\n"
            "Content-Description: Undelivered Message Headers\nContent-Type: text/rfc822-headers\n\n"
            f"Return-Path: <{OWN}>\nSubject: Our newsletter\n\n--{boundary}--\n").encode()


def generate(out_dir: str | Path, n: int, seed: int, holdout_share: float = 0.0, name: str = "set") -> dict:
    out = Path(out_dir)
    inbox = out / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    for old in inbox.glob("*.eml"):
        old.unlink()
    rng = random.Random(seed)
    people = [(f, l, d) for f in FIRST for l in LAST for d in DOMAINS]
    rng.shuffle(people)
    cats, weights = list(WEIGHTS), [WEIGHTS[c] for c in WEIGHTS]
    t = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
    replied: list[tuple] = []  # (person, time) of senders who got an auto-reply -> repeat-sender candidates
    labels: list[dict] = []

    for i in range(n):
        t += timedelta(seconds=rng.randint(15, 240))
        cat = rng.choices(cats, weights)[0]
        challenge = False
        repeat = False
        person = None
        if cat in HUMAN and replied and rng.random() < 0.08:
            recent = [p for p, rt in replied if (t - rt) < timedelta(hours=20)]
            if recent:
                person, repeat = rng.choice(recent), True
        if person is None:
            person = people.pop()
        ids = _ids(rng, t)
        mid = f"<{rng.getrandbits(80):020x}@{person[2]}>"
        tz = timezone(timedelta(hours=rng.choice([0, 1, -5, 5.5, 2, -8])))
        sent_local = t.astimezone(tz)
        label = dict(file=f"m{i:05d}.eml", message_id=mid, category=cat, challenge=0, is_duplicate=0,
                     duplicate_of="", expect_reply=0, expect_reason="", queue=QUEUE[cat], order_id="",
                     invoice_no="", amount="", bounced_address="", phrasing="")
        raw: bytes

        if cat == "bounce":
            bperson = people.pop()
            baddr, _ = _address(bperson)
            legacy = rng.random() < 0.35
            challenge = legacy
            bmid = f"<{rng.getrandbits(80):020x}@mx.example.net>"
            label["message_id"] = bmid
            raw = _bounce(rng, sent_local, baddr, legacy, bmid)
            label.update(bounced_address=baddr, expect_reason="machine")
        else:
            addr, address = _address(person)
            msg = EmailMessage(policy=policy.default)
            msg["From"] = address
            msg["To"] = OWN
            msg["Date"] = format_datetime(sent_local)
            msg["Message-ID"] = mid
            msg["MIME-Version"] = "1.0"
            if cat in HUMAN:
                pool, label["phrasing"] = _pick_pool(rng, holdout_share, cat)  # "A" = seen by the rules, "B" = written after the freeze
                usd = rng.random() < 0.25
                subject = _fill(rng.choice(pool["subjects"]), ids, usd)
                body = _fill(rng.choice(pool["bodies"]), ids, usd)
                if rng.random() < 0.12:  # mention another topic without changing intent
                    other = rng.choice([c for c in DISTRACTORS if c != cat])
                    body += " " + DISTRACTORS[other]
                    challenge = True
                if rng.random() < 0.15:
                    body = _typos(rng, body)
                    challenge = True
                if rng.random() < 0.5:
                    body += f"\n\n-- \n{address.display_name}\n{rng.choice(COMPANIES)}"
                elif rng.random() < 0.3:
                    body += "\n\nSent from my phone"
                if rng.random() < 0.1:
                    body += "\n\nThis email and any attachments are intended solely for the addressee."
                quoted_html = ""
                if rng.random() < 0.2:  # earlier conversation about a different topic, quoted below
                    other = rng.choice([c for c in HUMAN if c != cat])
                    old = _fill(rng.choice(POOL_A[other]["bodies"]), _ids(rng, t), False)
                    head = f"On {(t - timedelta(days=2)).strftime('%a, %d %b %Y')}, Support <{OWN}> wrote:"
                    body_plain = body + f"\n\n{head}\n" + "\n".join("> " + ln for ln in old.splitlines())
                    quoted_html = (f'<div class="gmail_quote"><div class="gmail_attr">{html.escape(head)}</div>'
                                   f'<blockquote class="gmail_quote">{html.escape(old)}</blockquote></div>')
                else:
                    body_plain = body
                msg["Subject"] = subject
                fmt = rng.random()
                if fmt < 0.5:
                    msg.set_content(body_plain)
                elif fmt < 0.7:
                    h = _html(body)
                    msg.set_content(h.replace("</body>", quoted_html + "</body>"), subtype="html")
                else:
                    msg.set_content(body_plain)
                    h = _html(body)
                    msg.add_alternative(h.replace("</body>", quoted_html + "</body>"), subtype="html")
                if cat in ("tech_support", "billing") and rng.random() < 0.1:
                    msg.add_attachment(b"timestamp,event\n09:01,error\n", maintype="text", subtype="csv",
                                       filename="attachment.csv")
                label["challenge"] = int(challenge)
                if cat in REPLY_CATS:
                    label.update(expect_reply=0 if repeat else 1, expect_reason="cooldown" if repeat else "reply")
                    if not repeat:
                        replied.append((person, t))
                else:
                    label["expect_reason"] = "suppress"
                if cat in ("order_status", "refund_request") and ids["ord"] in subject + body:
                    label["order_id"] = ids["_order"]
                if cat == "billing" and ids["inv"] in subject + body:
                    label["invoice_no"] = ids["_inv"]
                if cat in ("billing", "refund_request") and ids["amt"] in body:
                    label["amount"] = ids["_amt"]
            elif cat == "auto_reply":
                orig = rng.choice(["Order question", "Quick question", "Meeting notes", "Invoice follow-up"])
                body = rng.choice([
                    f"Thank you for your message. I am out of the office until {ids['date']} with limited access to "
                    "email. For urgent matters please contact my colleague.",
                    f"Hello, I am currently away from my desk and will reply after {ids['date']}. "
                    "This is an automated message."])
                headered = rng.random() < 0.7
                if headered:
                    msg["Auto-Submitted"] = "auto-replied"
                    msg["Subject"] = rng.choice([f"Automatic reply: {orig}", f"Out of Office: {orig}", f"Re: {orig}"])
                else:
                    msg["Subject"] = rng.choice([f"Automatic reply: {orig}", f"Re: {orig}"])
                    challenge = True
                msg.set_content(body)
                label.update(expect_reason="machine", challenge=int(challenge))
            else:  # bulk
                nl_name, nl_addr = rng.choice(NEWSLETTERS)
                del msg["From"]
                msg["From"] = Address(display_name=nl_name, addr_spec=nl_addr)
                body = ("This week in widgets: five tips for faster shipping.\n\nView this email in your browser.\n"
                        "You are receiving this email because you subscribed to our newsletter.\nUnsubscribe | Manage preferences")
                headers = rng.random() < 0.8
                if headers:
                    msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{nl_addr.split('@')[1]}>"
                    msg["Precedence"] = "bulk"
                else:
                    challenge = True
                msg["Subject"] = rng.choice(["Your weekly digest", "New this week", "Members-only offers"])
                msg.set_content(body)
                msg.add_alternative(_html(body, True), subtype="html")
                label.update(expect_reason="machine", challenge=int(challenge))
            random.seed(rng.getrandbits(64))  # email.generator draws MIME boundaries from the global RNG
            raw = msg.as_bytes()

        (inbox / label["file"]).write_bytes(raw)
        labels.append(label)
        if cat != "bounce" and rng.random() < 0.04:  # same message delivered twice (identical Message-ID)
            dup = dict(label, file=f"m{i:05d}-dup.eml", is_duplicate=1, duplicate_of=label["message_id"],
                       expect_reply=0, expect_reason="duplicate")
            (inbox / dup["file"]).write_bytes(raw)
            labels.append(dup)

    with open(out / "labels.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels)
    digest = write_manifest(out)
    return {"name": name, "n_files": len(labels), "n_unique": sum(1 for r in labels if not r["is_duplicate"]),
            "seed": seed, "sha256": digest}


def write_manifest(out: Path) -> str:
    lines = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}")
    text = "\n".join(lines) + "\n"
    (out / "MANIFEST.sha256").write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def read_labels(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
