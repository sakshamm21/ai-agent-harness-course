"""Pick the implementation under test: IMPL=starter (default) or IMPL=solution.

    IMPL=starter python3 -m pytest tests/test_part01_ingest.py   # your code
    IMPL=solution python3 -m pytest -q                           # the reference
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
os.environ["SUPPORTBOT_MOCK"] = "1"  # tests never call a real API

DATA = ROOT / "data"
HELP = DATA / "help_center"
POISONED = DATA / "poisoned"
SEED = DATA / "seed_orders.json"


def pytest_report_header(config):
    return f"supportbot implementation: {IMPL} ({ROOT / IMPL})"


@pytest.fixture(scope="session")
def index():
    from supportbot.ingest import build_index
    return build_index(HELP)


@pytest.fixture(scope="session")
def poisoned_index():
    from supportbot.ingest import build_index
    return build_index(HELP, POISONED)


@pytest.fixture
def store():
    from supportbot.tools import OrderStore
    return OrderStore(":memory:", seed=SEED)


@pytest.fixture
def mock():
    from supportbot.model import MockModel
    return MockModel()
