"""SQLite state machine. Every transition is one committed transaction (WAL, synchronous=FULL).

RECEIVED -> DONE                                  (no reply wanted: machine mail, unsubscribe, cooldown, review...)
RECEIVED -> QUEUED -> SENDING -> SENT             (reply wanted)
SENDING  -> SENT | QUEUED | REVIEW                (recovery after a crash, decided by the sent-ledger)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .parse import Mail

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(name TEXT PRIMARY KEY, message_id TEXT, duplicate INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS mail(
  message_id TEXT PRIMARY KEY, file TEXT NOT NULL, sender TEXT NOT NULL, sender_name TEXT, subject TEXT,
  sent_at TEXT NOT NULL, parsed TEXT NOT NULL, state TEXT NOT NULL, category TEXT, queue TEXT, reason TEXT,
  fields TEXT, ticket TEXT, reply_id TEXT, attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS suppression(address TEXT PRIMARY KEY, reason TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS mail_state ON mail(state, sent_at, file);
CREATE INDEX IF NOT EXISTS mail_sender ON mail(sender, sent_at);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def has_file(self, name: str) -> bool:
        return self.db.execute("SELECT 1 FROM files WHERE name=?", (name,)).fetchone() is not None

    def add_received(self, mail: Mail) -> bool:
        """Insert a parsed message. Returns False when the Message-ID was already seen (re-delivery)."""
        with self.tx() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO mail(message_id,file,sender,sender_name,subject,sent_at,parsed,state) "
                "VALUES(?,?,?,?,?,?,?,'RECEIVED')",
                (mail.message_id, mail.file, mail.sender, mail.sender_name, mail.subject, mail.sent_at,
                 json.dumps(mail.to_dict())))
            fresh = cur.rowcount == 1
            db.execute("INSERT INTO files(name,message_id,duplicate) VALUES(?,?,?)",
                       (mail.file, mail.message_id, 0 if fresh else 1))
        return fresh

    def rows(self, state: str):
        return self.db.execute("SELECT * FROM mail WHERE state=? ORDER BY sent_at, file", (state,)).fetchall()

    def finish_triage(self, mid: str, state: str, decision, fields: dict, ticket: str, reply_id: str,
                      reason: str, suppress: list[tuple[str, str]]):
        with self.tx() as db:
            db.execute("UPDATE mail SET state=?,category=?,queue=?,reason=?,fields=?,ticket=?,reply_id=? "
                       "WHERE message_id=? AND state='RECEIVED'",
                       (state, decision.category, decision.queue, reason, json.dumps(fields), ticket, reply_id, mid))
            for addr, why in suppress:
                db.execute("INSERT OR IGNORE INTO suppression(address,reason) VALUES(?,?)", (addr, why))

    def transition(self, mid: str, new: str, expect: str | tuple, bump_attempts: bool = False):
        expect = (expect,) if isinstance(expect, str) else expect
        marks = ",".join("?" * len(expect))
        with self.tx() as db:
            cur = db.execute(f"UPDATE mail SET state=?, attempts=attempts+? WHERE message_id=? AND state IN ({marks})",
                             (new, 1 if bump_attempts else 0, mid, *expect))
            if cur.rowcount != 1:
                raise RuntimeError(f"illegal transition {expect} -> {new} for {mid}")

    def recent_reply(self, sender: str, sent_at_iso: str, hours: int = 24) -> bool:
        lo = (datetime.fromisoformat(sent_at_iso) - timedelta(hours=hours)).isoformat()
        return self.db.execute(
            "SELECT 1 FROM mail WHERE sender=? AND sent_at>=? AND sent_at<=? AND state IN ('QUEUED','SENDING','SENT') LIMIT 1",
            (sender, lo, sent_at_iso)).fetchone() is not None

    def is_suppressed(self, address: str) -> bool:
        return self.db.execute("SELECT 1 FROM suppression WHERE address=?", (address,)).fetchone() is not None

    def counts(self) -> dict:
        return {r["state"]: r["n"] for r in self.db.execute("SELECT state, COUNT(*) n FROM mail GROUP BY state")}

    def all_rows(self):
        return self.db.execute("SELECT * FROM mail ORDER BY sent_at, file").fetchall()

    def close(self):
        self.db.close()
