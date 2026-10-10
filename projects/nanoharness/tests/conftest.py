"""Put starter/ or solution/ on sys.path. IMPL=starter (default) tests your code; IMPL=solution
tests the reference. Every test works inside pytest's tmp_path and never touches anything else."""
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPL = os.environ.get("IMPL", "starter")
if IMPL not in ("starter", "solution"):
    raise SystemExit(f"IMPL must be 'starter' or 'solution', not {IMPL!r}")
IMPL_DIR = os.path.join(PROJECT, IMPL)
sys.path.insert(0, IMPL_DIR)
for name in [m for m in sys.modules if m == "nanoharness" or m.startswith("nanoharness.")]:
    del sys.modules[name]  # never test a copy imported from somewhere else


def pytest_report_header(config):
    return f"nanoharness implementation: {IMPL_DIR}"
