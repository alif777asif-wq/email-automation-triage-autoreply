#!/usr/bin/env bash
# One command: create a virtualenv, install the pinned dependencies, regenerate the data,
# run the tests, the evaluation and the crash campaigns, and write everything to results/.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
pip install --quiet --disable-pip-version-check -r requirements.txt
PYTHONPATH=src python -m mailtriage reproduce
