"""Machine-mail format sets: automated mail as real systems send it, with and without the standard markers.

The main test set (datagen.py) builds its machine mail from a few templates the rules were written against, so a 100% score
there says little about mail from systems the author never saw. These sets add that missing measurement.

    formats-a   14 formats x 14 messages. Written AFTER the main test; the first result on it showed unmarked automated mail
                being answered. It is the development set of guard.py.
    formats-b   14 different formats x 14 messages. Written AFTER guard.py was frozen (hash in data/RULES_FROZEN.sha256) and
                never used to change guard.py. It did show what the wording guard misses, so it is a development set of roles.py.
    formats-c   14 further formats x 14 messages. Written AFTER roles.py was frozen and never used to change it: the held-out
                set for the whole guard. Same author as the rules, so held out, not independent.

Every message is machine mail: the right outcome is never an automatic reply. `marked` records whether the message carries a
standard marker (an Auto-Submitted / Precedence / List-* header, DSN structure, or a mailer-daemon / postmaster / no-reply /
notifications sender). Every sender address is unique so the 24 h cooldown cannot hide a wrongly answered message.
All domains are RFC 2606 reserved; every name is fictional.
"""
from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Callable

from .datagen import FIRST, LAST, OWN, write_manifest

LABEL_FIELDS = ["file", "message_id", "category", "format", "marked", "expect_reply"]
ORIG_SUBJECTS = ["Order question", "Invoice INV-2026-0042 follow up", "Quick question", "Where is my parcel?", "Meeting notes",
                 "Pricing for 25 seats", "Following up", "Delivery address change"]


class Ctx:
    """Everything a template needs: a seeded RNG, the message index and small helpers. Index makes every sender unique."""

    def __init__(self, rng: random.Random, i: int):
        self.rng, self.i = rng, i
        self.when = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=7 * i)
        self.date = format_datetime(self.when)

    def mid(self, domain: str = "mx.example.net") -> str:
        return f"<{self.rng.getrandbits(80):020x}@{domain}>"

    def person(self) -> tuple[str, str, str]:
        (f, fa), (l, la) = self.rng.choice(FIRST), self.rng.choice(LAST)
        self.first_slug = fa  # ASCII form of the first name, for local parts
        return f"{f} {l}", f, f"{fa}.{la}{self.i}@{self.rng.choice(['example.com', 'example.org', 'example.net'])}"

    def host(self, stem: str, tld: str = "example.com") -> str:
        return f"{stem}{self.i:03d}.{tld}"

    def later(self, days_lo: int = 3, days_hi: int = 20, fmt: str = "%d %B") -> str:
        return (self.when + timedelta(days=self.rng.randint(days_lo, days_hi))).strftime(fmt)

    def orig(self) -> str:
        return self.rng.choice(ORIG_SUBJECTS)

    def message(self, name: str, addr: str, subject: str, body: str, headers: dict | None = None) -> bytes:
        m = EmailMessage(policy=policy.default)
        m["From"] = Address(display_name=name, addr_spec=addr)
        m["To"] = OWN
        m["Date"] = self.date
        m["Message-ID"] = self.mid()
        m["Subject"] = subject
        for k, v in (headers or {}).items():
            m[k] = v
        m.set_content(body)
        random.seed(self.rng.getrandbits(64))  # email.generator draws MIME boundaries from the global RNG
        return m.as_bytes()

    def raw(self, text: str) -> bytes:
        return text.encode()


@dataclass(frozen=True)
class Format:
    name: str
    category: str  # auto_reply | bounce | bulk
    marked: bool
    build: Callable[[Ctx], bytes]


SET_NAMES = ("formats-a", "formats-b", "formats-c")


def spec_for(name: str) -> dict:
    """The template modules import Format and Ctx from here, so they are imported lazily to avoid a cycle."""
    from . import formats_a, formats_b, formats_c
    return {"formats-a": dict(seed=301, per_format=14, formats=formats_a.FORMATS),
            "formats-b": dict(seed=302, per_format=14, formats=formats_b.FORMATS),
            "formats-c": dict(seed=303, per_format=14, formats=formats_c.FORMATS)}[name]


def generate_formats(out_dir: str | Path, name: str) -> dict:
    spec = spec_for(name)
    out = Path(out_dir)
    inbox = out / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    for old in inbox.glob("*.eml"):
        old.unlink()
    rng = random.Random(spec["seed"])
    labels, i = [], 0
    for fmt in spec["formats"]:
        for _ in range(spec["per_format"]):
            ctx = Ctx(rng, i)
            raw = fmt.build(ctx)
            fname = f"f{i:04d}.eml"
            (inbox / fname).write_bytes(raw)
            mid = next(ln for ln in raw.decode().splitlines() if ln.lower().startswith("message-id:")).split(":", 1)[1].strip()
            labels.append(dict(file=fname, message_id=mid, category=fmt.category, format=fmt.name, marked=int(fmt.marked), expect_reply=0))
            i += 1
    with open(out / "labels.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels)
    digest = write_manifest(out)
    return {"name": name, "n_files": len(labels), "n_formats": len(spec["formats"]), "seed": spec["seed"], "sha256": digest}
