"""Process helpers shared by the evaluation, the crash tests and the pytest suite."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def child_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("MAILTRIAGE_CRASH", None)
    env.pop("MAILTRIAGE_SEND_DELAY_MS", None)
    env.update(extra or {})
    return env


class SinkProcess:
    """A real SMTP server in its own process; it keeps running while pipeline processes are killed."""

    def __init__(self, directory: Path, port: int | None = None):
        self.dir, self.port = Path(directory), port or free_port()
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "SinkProcess":
        self.dir.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen([sys.executable, "-m", "mailtriage.smtp_sink", "--dir", str(self.dir),
                                      "--port", str(self.port)], env=child_env(), stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                return self
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("SMTP sink did not start")

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=10)


def run_cli(args: list[str], env: dict | None = None, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "mailtriage", *args], env=child_env(env), capture_output=True,
                          text=True, timeout=timeout)


def popen_cli(args: list[str], env: dict | None = None) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "mailtriage", *args], env=child_env(env),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
