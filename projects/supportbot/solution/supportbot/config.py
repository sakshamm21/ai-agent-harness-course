"""Paths and settings shared by every part. Infrastructure: you do not need to edit it."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]          # projects/supportbot/
DATA_DIR = Path(os.environ.get("SUPPORTBOT_DATA", PROJECT_ROOT / "data"))
HELP_DIR = DATA_DIR / "help_center"
POISONED_DIR = DATA_DIR / "poisoned"
SEED_ORDERS = DATA_DIR / "seed_orders.json"
EVALS = DATA_DIR / "evals.jsonl"
RUNS_DIR = Path(os.environ.get("SUPPORTBOT_RUNS", PROJECT_ROOT / "runs"))   # traces, sqlite db
STATIC_DIR = Path(__file__).resolve().parent / "static"

REFUND_APPROVAL_LIMIT = 100.00   # refunds above this need a human (part 5)
