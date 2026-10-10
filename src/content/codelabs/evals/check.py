# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
_keys = {"id", "category", "question", "must_include", "must_not_include"}
_cats = {}
for _c in CASES:
    _cats[_c.get("category")] = _cats.get(_c.get("category"), 0) + 1
check("at least 20 well-formed cases with unique ids",
      len(CASES) >= 20 and all(_keys <= set(_c) for _c in CASES) and len({_c["id"] for _c in CASES}) == len(CASES),
      "Each case needs id, category, question, must_include and must_not_include. Ids must be unique.")
check("at least 4 categories, each with 3 or more cases", len(_cats) >= 4 and min(_cats.values()) >= 3,
      "Use the five categories: refund, order_status, cancel, account, escalation.")
check("at least 5 cases say what must NOT appear", sum(1 for _c in CASES if _c["must_not_include"]) >= 5,
      "Negative checks catch the dangerous answers: a refund outside the window, a cancel of a shipped order.")

_t = {"must_include": ["Refund", "$35"], "must_not_include": ["can't"]}
check("grade passes a matching answer (case-insensitive)", grade(_t, "I've started a REFUND of $35."))
check("grade fails a missing must_include", not grade(_t, "I've started a refund."), "Every must_include string has to appear.")
check("grade fails a forbidden string", not grade(_t, "Refund of $35? Sorry, I can't."), "No must_not_include string may appear.")

_fake_cases = [
    {"id": "x1", "category": "a", "question": "q1", "must_include": ["yes"], "must_not_include": []},
    {"id": "x2", "category": "a", "question": "q2", "must_include": ["yes"], "must_not_include": []},
    {"id": "x3", "category": "b", "question": "q3", "must_include": ["yes"], "must_not_include": []},
    {"id": "x4", "category": "b", "question": "q4", "must_include": ["yes"], "must_not_include": ["no"]},
]
_s = score(lambda q: {"q1": "yes", "q2": "nope", "q3": "yes", "q4": "yes and no"}[q], _fake_cases)
check("score reports overall and per-category pass rates",
      abs(_s.get("overall", -1) - 0.5) < 1e-9 and _s.get("by_category") == {"a": 0.5, "b": 0.5}
      and sorted(_s.get("failed", [])) == ["x2", "x4"],
      "On 4 cases with 2 passes: overall 0.5, by_category {'a': 0.5, 'b': 0.5}, failed ['x2', 'x4'].")

_o = {"overall": 0.9, "by_category": {"refund": 1.0, "account": 0.5}}
check("should_ship blocks a candidate whose average holds but one category drops",
      should_ship(_o, {"overall": 0.9, "by_category": {"refund": 0.6, "account": 1.0}}) is False
      and should_ship(_o, {"overall": 0.95, "by_category": {"refund": 1.0, "account": 0.75}}) is True,
      "Compare every category, not just the overall number.")

_v1 = score(v1, CASES)
check("your cases describe the trusted agent: v1 passes at least 80%", _v1.get("overall", 0) >= 0.8,
      "Press Run and read what v1 answers. Cases v1 fails are either real bugs or wrong expectations.")
_caught = [c["id"] for c in CASES if grade(c, v1(c["question"])) and not grade(c, v2(c["question"]))]
check("your eval set catches v2's regression (a case v1 passes and v2 fails)", len(_caught) >= 1,
      "Ask for a refund on A-1002 or A-1005 (delivered 45 and 31 days ago) and forbid \"started a refund\".")
check("the ship decision is no", ship_v2 is False, "v2's average ties v1, but its refund category dropped.")
