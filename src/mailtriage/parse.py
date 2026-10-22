"""RFC 5322 / MIME parsing into a small normalised record."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

QUOTE_CUTS = [
    re.compile(r"^On\b[^\n]{0,200}(?:\n[^\n]{0,200})?wrote:\s*$", re.I | re.M),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.I | re.M),
    re.compile(r"^-{3,}\s*Forwarded message\s*-{3,}", re.I | re.M),
    re.compile(r"^From:[^\n]+\n(?:Sent|Date):", re.I | re.M),
]
NOREPLY = re.compile(r"^(no[-_.]?reply|do[-_.]?not[-_.]?reply|notifications?|mailer-daemon|postmaster|bounces?)", re.I)


class _Text(HTMLParser):
    """HTML -> text. Drops <head>, <script>, <style> and quoted <blockquote> history."""
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table"}
    SKIP = {"head", "script", "style", "title", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(src: str) -> str:
    p = _Text()
    p.feed(src)
    return re.sub(r"\n{3,}", "\n\n", "".join(p.out)).strip()


def strip_quoted(text: str) -> str:
    """Remove quoted history, signature and '> ' lines so only the new message is classified."""
    cut = len(text)
    for rx in QUOTE_CUTS:
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]
    text = re.split(r"^-- ?$", text, maxsplit=1, flags=re.M)[0]  # RFC 3676 signature delimiter
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    text = re.sub(r"^Sent from my .*$", "", text, flags=re.M | re.I)
    return text.strip()


@dataclass
class Mail:
    message_id: str
    file: str
    sender: str
    sender_name: str
    subject: str
    sent_at: str  # ISO 8601, UTC
    body: str
    dsn_text: str = ""
    attachments: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Mail":
        return Mail(**d)


def parse_bytes(raw: bytes, file: str = "") -> Mail:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    mid = (str(msg["Message-ID"] or "")).strip()
    if not mid:  # never trust a missing id: derive a stable one from the content
        mid = f"<sha256-{hashlib.sha256(raw).hexdigest()[:24]}@generated.invalid>"
    name, addr = parseaddr(str(msg["From"] or ""))
    try:
        dt = parsedate_to_datetime(str(msg["Date"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        sent = dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        sent = datetime(1970, 1, 1, tzinfo=timezone.utc)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    text = ""
    if body_part is not None:
        text = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            text = html_to_text(text)
    dsn_text = "\n".join(p.as_string() for p in msg.walk() if p.get_content_type() == "message/delivery-status")
    attachments = [p.get_filename() for p in msg.walk() if p.get_filename()]
    ctype = msg.get_content_type()
    local = addr.split("@")[0] if "@" in addr else addr
    auto = str(msg["Auto-Submitted"] or "").strip().lower()
    flags = {
        "is_dsn": ctype == "multipart/report" or "delivery-status" in str(msg.get("Content-Type", "")).lower()
                  or local.lower() in ("mailer-daemon", "postmaster"),
        "auto_submitted": bool(auto) and auto != "no",
        "x_autoreply": any(msg.get(h) for h in ("X-Autoreply", "X-Autorespond")),
        "precedence": str(msg["Precedence"] or "").strip().lower(),
        "list_headers": bool(msg["List-Id"] or msg["List-Unsubscribe"]),
        "noreply_sender": bool(NOREPLY.match(local)),
        "null_return_path": str(msg["Return-Path"] or "").strip() == "<>",
    }
    return Mail(message_id=mid, file=file, sender=addr.lower(), sender_name=name, subject=str(msg["Subject"] or ""),
                sent_at=sent.isoformat(), body=strip_quoted(text), dsn_text=dsn_text, attachments=attachments,
                flags=flags)


def parse_file(path: str | Path) -> Mail:
    p = Path(path)
    return parse_bytes(p.read_bytes(), p.name)
