"""Regenerate starter/ from solution/: each part function keeps its docstring, its body becomes
raise NotImplementedError("Part N: ..."). Run after changing solution/: python3 scripts/make_starter.py
"""
import ast
import shutil
from pathlib import Path
root = Path(__file__).resolve().parents[1]
src, dst = root / "solution", root / "starter"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
STUBS = {
 "ingest.py": (1, {"parse_article": "parse one article", "chunk_article": "split an article into chunks",
                   "embed": "turn text into a vector", "VectorIndex.search": "search the index",
                   "build_index": "load, chunk and embed the help center"}),
 "rag.py": (2, {"retrieve": "retrieve the best chunks", "build_messages": "put the documents in the prompt",
                "extract_citations": "find [article-id] citations", "check_citations": "reject made-up citations",
                "answer": "retrieve, ask, verify"}),
 "tools.py": (3, {"lookup_order": "look an order up", "check_refundable": "check a refund is allowed",
                  "issue_refund": "refund exactly once per idempotency key", "escalate_to_human": "open a ticket",
                  "make_idempotency_key": "derive the idempotency key", "run_tool": "validate, run and wrap a tool call"}),
 "router.py": (4, {"rule_route": "route with keyword rules", "parse_label": "parse the router's label",
                   "route": "route with the small model"}),
 "agent.py": (4, {"SupportAgent.handle": "the agent loop"}),
 "guardrails.py": (5, {"redact_pii": "redact PII", "needs_approval": "the approval threshold",
                       "refund_gate": "hold big refunds for a person", "approve_refund": "issue an approved refund"}),
 "security.py": (6, {"sanitize_document": "strip hidden text", "injection_signals": "flag injection patterns",
                     "wrap_untrusted": "wrap documents as untrusted", "authorize_tool_call": "the trust boundary"}),
 "evals.py": (7, {"check_tool_calls": "exact tool-call checks", "parse_judgment": "parse the judge's verdict",
                  "judge": "ask the judge", "run_suite": "run the eval set"}),
 "tracing.py": (8, {"Tracer.write": "append a redacted event", "load_trace": "read a JSONL trace",
                    "timeline": "turn events into timeline rows", "summarize": "summarize a trace"}),
}
for fname, (part, funcs) in STUBS.items():
    path = dst / "supportbot" / fname
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    edits = []
    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, node.name + ".")
            elif isinstance(node, ast.FunctionDef) and prefix + node.name in funcs:
                q = prefix + node.name
                first = node.body[0]
                has_doc = isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str)
                start = (first.end_lineno if has_doc else first.lineno - 1)  # 0-based index of first line to replace
                end = node.body[-1].end_lineno
                indent = " " * (first.col_offset)
                stub = f'{indent}raise NotImplementedError("Part {part}: {funcs[q]} ({node.name})")\n'
                edits.append((start, end, stub)); funcs_found.add(q)
    funcs_found = set()
    visit(tree.body)
    missing = set(funcs) - funcs_found
    assert not missing, (fname, missing)
    for start, end, stub in sorted(edits, reverse=True):
        lines[start:end] = [stub]
    path.write_text("".join(lines))
    print(fname, sorted(funcs_found))
