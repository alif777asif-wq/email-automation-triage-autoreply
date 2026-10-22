import re
from pathlib import Path

from mailtriage import datagen


def test_generation_is_byte_for_byte_reproducible(tmp_path):
    a = datagen.generate(tmp_path / "a", 60, 9, 0.5)
    b = datagen.generate(tmp_path / "b", 60, 9, 0.5)
    assert a["sha256"] == b["sha256"]


def test_labels_cover_every_file_and_use_only_reserved_domains(small_set):
    rows = datagen.read_labels(small_set / "labels.csv")
    files = {p.name for p in (small_set / "inbox").glob("*.eml")}
    assert files == {r["file"] for r in rows}
    text = "".join(p.read_text(errors="ignore") for p in (small_set / "inbox").glob("*.eml"))
    domains = set(re.findall(r"@([A-Za-z0-9.-]+\.[a-z]+)", text))
    assert domains and all(d.endswith(("example.com", "example.org", "example.net", ".example")) for d in domains), domains


def test_redeliveries_share_message_id_with_original(small_set):
    rows = {r["file"]: r for r in datagen.read_labels(small_set / "labels.csv")}
    dups = [r for r in rows.values() if r["is_duplicate"] == "1"]
    for d in dups:
        assert d["message_id"] == d["duplicate_of"]
        assert (small_set / "inbox" / d["file"]).read_bytes() == (small_set / "inbox" / d["file"].replace("-dup", "")).read_bytes()
