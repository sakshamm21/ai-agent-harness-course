"""Pick the implementation under test: IMPL=starter (default) or IMPL=solution.

    IMPL=starter python3 -m pytest tests/test_part01_orchestrator.py   # your code
    IMPL=solution python3 -m pytest -q                                 # the reference
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMPL = os.environ.get("IMPL", "starter")
if IMPL not in ("starter", "solution"):
    raise SystemExit(f"IMPL must be 'starter' or 'solution', not {IMPL!r}")
sys.path.insert(0, str(ROOT / IMPL))
os.environ["DEEPRESEARCH_MOCK"] = "1"  # tests never call a real API


def pytest_report_header(config):
    return f"deepresearch implementation: {IMPL} ({ROOT / IMPL})"


@pytest.fixture(scope="session")
def corpus():
    from deepresearch.corpus import Corpus
    return Corpus.load()


@pytest.fixture
def models():
    from deepresearch.model import get_models
    return get_models(mock=True)
