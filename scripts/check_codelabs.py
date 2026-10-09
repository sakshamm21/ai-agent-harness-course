"""For every code lab: the starter must fail at least one check and the solution must pass all.

Run: python3 scripts/check_codelabs.py [lab-id ...]
Uses CPython with python/ on the path, mirroring what the browser runner does in Pyodide.
"""
import io
import os
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))
LABS = ROOT / "src" / "content" / "codelabs"


def run(code: str, check_code: str):
    results = []

    def check(label, cond, hint=""):
        results.append((label, bool(cond)))

    for m in [m for m in sys.modules if m.startswith("agentkit_mini")]:
        del sys.modules[m]
    os.environ["FAH_REAL_MODEL"] = "0"
    ns = {"__name__": "__main__", "check": check}
    buf = io.StringIO()
    err = None
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            exec(compile(code, "lab.py", "exec"), ns)
            exec(compile(check_code, "check.py", "exec"), ns)
    except Exception:
        err = traceback.format_exc(limit=3)
    return results, err, buf.getvalue()


def main(ids):
    bad = 0
    for d in sorted(LABS.iterdir()):
        if ids and d.name not in ids:
            continue
        chk = (d / "check.py").read_text()
        s_res, s_err, _ = run((d / "starter.py").read_text(), chk)
        o_res, o_err, o_out = run((d / "solution.py").read_text(), chk)
        starter_fails = bool(s_err) or not s_res or not all(ok for _, ok in s_res)
        solution_ok = not o_err and o_res and all(ok for _, ok in o_res)
        status = "ok " if starter_fails and solution_ok else "BAD"
        if status == "BAD":
            bad += 1
        print(f"{status} {d.name}: starter {'fails' if starter_fails else 'PASSES (should fail)'}; solution "
              f"{'passes' if solution_ok else 'FAILS'} ({sum(ok for _, ok in o_res)}/{len(o_res)})")
        if not solution_ok:
            print("   ", o_err or [l for l, ok in o_res if not ok])
            print("    output:", o_out[-800:])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
