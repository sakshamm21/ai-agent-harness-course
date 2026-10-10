"""Part 5: the report writer: a structured handoff in, Markdown with numbered sources out."""
import os
import subprocess
import sys
from pathlib import Path

from deepresearch.model import MockModel, ResearchMock, Response
from deepresearch.records import Claim, WorkerResult
from deepresearch.writer import build_handoff, number_citations, parse_report, write_report

ROOT = Path(__file__).resolve().parents[1]
RESULTS = [
    WorkerResult("When did the Velmora Tunnel open?", "ok",
                 [Claim("The Velmora Tunnel opened to passenger trains on 14 June 2019.", ["vt-01"])], ["vt-01"]),
    WorkerResult("How much did it cost (Velmora Tunnel)?", "ok",
                 [Claim("The Velmora Tunnel cost 6.2 billion crowns to build.", ["vt-03", "vt-01"])], ["vt-01", "vt-03"]),
    WorkerResult("Who painted it (Velmora Tunnel)?", "empty"),
]


def test_handoff_groups_claims_and_lists_gaps(corpus):
    h = build_handoff("Q?", RESULTS, corpus)
    assert [s["sub_question"] for s in h["sections"]] == [r.sub_question for r in RESULTS[:2]]
    assert h["gaps"] == ["Who painted it (Velmora Tunnel)?"]
    assert set(h["sources"]) == {"vt-01", "vt-03"}


def test_number_citations_in_order_of_first_use(corpus):
    md = "# Q\n\n- First [vt-03].\n- Second [vt-01, vt-03].\n"
    out = number_citations(md, corpus, {"vt-01", "vt-03"})
    assert "- First [1]." in out and "- Second [1, 2]." in out
    src = out.split("## Sources", 1)[1]
    assert src.index("1. Velmora Tunnel final bill") < src.index("2. Velmora Tunnel opens")
    assert "corpus://" in src


def test_number_citations_removes_ids_outside_the_handoff(corpus):
    out = number_citations("- Claim [kw-01].\n- Other [vt-01].\n", corpus, {"vt-01"})
    assert "kw-01" not in out and "- Claim." in out and "- Other [1]." in out


def test_write_report_with_the_mock_writer(corpus):
    md = write_report("When did the Velmora Tunnel open and what did it cost?", RESULTS, ResearchMock(), corpus)
    assert md.startswith("# When did the Velmora Tunnel open")
    assert "## Sources" in md and "## Gaps" in md and "Who painted it" in md
    cited, num_to_id = parse_report(md)
    assert set(num_to_id.values()) == {"vt-01", "vt-03"}
    assert all(ids for _, ids in cited)


def test_writer_sees_the_handoff_not_the_transcripts(corpus):
    spy = MockModel([Response(text="# Q\n\n- x [vt-01].\n")])
    seen = []
    orig = spy.complete
    spy.complete = lambda messages, **kw: (seen.append(messages), orig(messages, **kw))[1]
    write_report("Q", RESULTS, spy, corpus)
    text = seen[0][0]["content"]
    assert "Findings (JSON)" in text and "tool_result" not in text


def test_partial_reports_say_so(corpus):
    md = write_report("Q", RESULTS, ResearchMock(), corpus, partial=True)
    assert md.splitlines()[0] == "# Q" and "Partial report" in md


def test_no_findings_still_gives_a_report(corpus):
    md = write_report("Q", [RESULTS[2]], ResearchMock(), corpus)
    assert md.startswith("# Q") and "Not answered" in md and "## Sources" not in md


def test_cli_runs_end_to_end_on_the_mock():
    env = {**os.environ, "PYTHONPATH": str(ROOT / os.environ.get("IMPL", "starter")), "DEEPRESEARCH_MOCK": "1"}
    p = subprocess.run([sys.executable, "-m", "deepresearch", "How tall is the Harrow Point lighthouse?"],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("# How tall is the Harrow Point lighthouse?")
    assert "41 metres" in p.stdout and "## Sources" in p.stdout
