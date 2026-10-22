"""A real local SMTP server that records every message it accepts.

It stands in for the outside world: the pipeline talks to it over genuine SMTP, and the tests
count what it *received*, independent of anything the pipeline believes it sent.
Each accepted message -> inbox/NNNNNN.eml and one fsynced line in ledger.jsonl before '250 OK'.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from email import policy
from email.parser import BytesParser
from pathlib import Path

from aiosmtpd.controller import Controller


class SinkHandler:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        (self.dir / "inbox").mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.dir / "ledger.jsonl"
        self.seq = len(list((self.dir / "inbox").glob("*.eml")))

    async def handle_DATA(self, server, session, envelope):
        raw = envelope.original_content
        msg = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
        self.seq += 1
        path = self.dir / "inbox" / f"{self.seq:06d}.eml"
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, path)
        entry = {"seq": self.seq, "message_id": str(msg["Message-ID"] or ""), "in_reply_to": str(msg["In-Reply-To"] or ""),
                 "mail_from": envelope.mail_from, "rcpt_to": envelope.rcpt_tos}
        with open(self.ledger_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return "250 OK"


class Ledger:
    """What the sender consults after a crash. Stands in for 'search the Sent folder / provider log by Message-ID'."""

    def __init__(self, directory: str | Path):
        self.path = Path(directory) / "ledger.jsonl"

    def available(self) -> bool:
        return self.path.exists()

    def message_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        with open(self.path, encoding="utf-8") as fh:
            return {json.loads(line)["message_id"] for line in fh if line.strip()}

    def contains(self, message_id: str) -> bool:
        return message_id in self.message_ids()


def serve(directory: str, port: int, host: str = "127.0.0.1") -> None:
    handler = SinkHandler(directory)
    Path(directory, "ledger.jsonl").touch()
    controller = Controller(handler, hostname=host, port=port)
    controller.start()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()
    controller.stop()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--port", type=int, required=True)
    a = ap.parse_args()
    serve(a.dir, a.port)


if __name__ == "__main__":
    main()
