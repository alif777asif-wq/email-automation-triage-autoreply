import pytest

from mailtriage import datagen
from mailtriage.parse import parse_bytes


@pytest.fixture(scope="session")
def small_set(tmp_path_factory):
    d = tmp_path_factory.mktemp("small")
    datagen.generate(d, 80, 5, holdout_share=0.5, name="small")
    return d


def mail(raw: str):
    return parse_bytes(raw.replace("\n", "\r\n").encode("utf-8"), "t.eml")


HEAD = "From: Ana Test <ana@example.com>\nTo: support@shop.example\nDate: Mon, 02 Mar 2026 09:00:00 +0000\nMessage-ID: <t1@example.com>\n"
