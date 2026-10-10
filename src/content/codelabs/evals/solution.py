import json
import re
from agentkit_mini import MockModel, Response, ToolCall, tool, run_loop

# ---------- The support agent under test (do not edit this part) ----------
ORDERS = {
    "A-1001": {"item": "headphones", "status": "delivered", "days_ago": 12, "price": 89},
    "A-1002": {"item": "desk lamp", "status": "delivered", "days_ago": 45, "price": 35},
    "A-1003": {"item": "mug", "status": "in transit", "eta": "Thursday", "price": 14},
    "A-1004": {"item": "backpack", "status": "processing", "price": 60},
    "A-1005": {"item": "keyboard", "status": "delivered", "days_ago": 31, "price": 120},
}


@tool
def get_order(order_id: str) -> dict:
    """Gets an order's item, status, delivery age in days and price by order id (like A-1001)."""
    return ORDERS.get(order_id.upper(), {"error": f"no order {order_id}"})


def _reply(q, version, oid, o):
    """What the scripted model says once it has seen the order."""
    if "error" in o:
        return f"I couldn't find order {oid}. Please check the id (it looks like A-1001)."
    wants_refund = any(w in q for w in ("refund", "money back", "return"))
    if wants_refund and o["status"] == "delivered":
        if o["days_ago"] <= 30 or version == "v2":   # v2's "friendlier" prompt drops the window check
            return f"Good news: I've started a refund of ${o['price']} for order {oid} ({o['item']})."
        return (f"Order {oid} was delivered {o['days_ago']} days ago, outside our 30-day refund window, "
                "so I can't refund it. I can offer a repair instead.")
    if wants_refund and o["status"] == "in transit":
        return f"Order {oid} is still in transit (arriving {o['eta']}). You can request a refund once it arrives."
    if (wants_refund or "cancel" in q) and o["status"] == "processing":
        return f"Order {oid} hasn't shipped yet, so I've cancelled it and refunded ${o['price']}."
    if "cancel" in q:
        return f"Order {oid} has already shipped, so it can't be cancelled. You can return it after delivery."
    eta = f", arriving {o['eta']}" if o.get("eta") else ""
    return f"Order {oid} ({o['item']}) is {o['status']}{eta}."


def make_agent(version):
    """Returns ask(question) -> answer text. v1 is in production; v2 is the candidate."""
    def script(messages, tools):
        q = messages[0]["content"].lower()
        last = messages[-1]["content"]
        m = re.search(r"a-\d{4}", q)
        if isinstance(last, list) and any(b.get("type") == "tool_result" for b in last):
            return Response(text=_reply(q, version, m.group(0).upper(), json.loads(last[0]["content"])))
        if any(w in q for w in ("lawyer", "sue", "chargeback", "complaint")):
            return Response(text="I'm sorry about this. I'm handing you to a human agent, who will reply within 24 hours.")
        if m:
            return Response(tool_calls=[ToolCall("c1", "get_order", {"order_id": m.group(0).upper()})])
        if "password" in q or (version == "v2" and any(w in q for w in ("log in", "login", "locked out", "sign in"))):
            return Response(text="To reset your password, go to Settings > Security > Reset password. We'll email you a link.")
        if any(w in q for w in ("refund", "return", "cancel", "order")):
            return Response(text="Please send your order id (it looks like A-1001) so I can check.")
        return Response(text="I can help with orders, refunds, cancellations and passwords. Could you tell me more?")

    model = MockModel(script)
    return lambda question: run_loop(model, [get_order], question, max_turns=4).final_text


v1 = make_agent("v1")
v2 = make_agent("v2")
# ---------------------------------------------------------------------------

# A case: the question, what a correct answer must contain, and what it must never contain.
# Matching is case-insensitive substring matching. Press Run to see what v1 actually says.
def case(id, category, question, include, exclude=()):
    return {"id": id, "category": category, "question": question,
            "must_include": list(include), "must_not_include": list(exclude)}


CASES = [
    case("r1", "refund", "My headphones from order A-1001 broke. Can I get a refund?", ["refund", "$89"], ["can't refund"]),
    case("r2", "refund", "I want my money back for the lamp, order A-1002.", ["30-day"], ["started a refund"]),
    case("r3", "refund", "Refund order A-1005 please, the keyboard is sticky.", ["outside"], ["started a refund"]),
    case("r4", "refund", "Can I return order A-1003? I changed my mind.", ["in transit"], ["started a refund"]),
    case("r5", "refund", "I'd like a refund.", ["order id"], ["started a refund"]),
    case("s1", "order_status", "Where is my order A-1003?", ["in transit", "thursday"]),
    case("s2", "order_status", "Has A-1001 been delivered?", ["delivered"]),
    case("s3", "order_status", "What's happening with A-1004?", ["processing"]),
    case("s4", "order_status", "Status of order A-7777?", ["couldn't find"], ["delivered"]),
    case("c1", "cancel", "Please cancel order A-1004.", ["cancelled"]),
    case("c2", "cancel", "Cancel A-1001, I don't need it.", ["can't be cancelled"], ["cancelled it"]),
    case("c3", "cancel", "Can you cancel my order A-1003?", ["already shipped"], ["cancelled it"]),
    case("c4", "cancel", "I want to cancel my order.", ["order id"]),
    case("a1", "account", "I forgot my password.", ["reset password"]),
    case("a2", "account", "I'm locked out of my account.", ["reset password"]),
    case("a3", "account", "I can't log in to my account.", ["reset password"]),
    case("e1", "escalation", "This is a joke. I'm filing a chargeback.", ["human"], ["refund"]),
    case("e2", "escalation", "My lawyer will hear about order A-1002.", ["human"], ["started a refund"]),
    case("e3", "escalation", "I want to make a formal complaint.", ["human"]),
    case("e4", "escalation", "I'll sue if this isn't fixed today.", ["human"]),
]


def grade(case, answer):
    """True when the answer contains every must_include string and no must_not_include string."""
    a = answer.lower()
    return (all(s.lower() in a for s in case["must_include"])
            and not any(s.lower() in a for s in case["must_not_include"]))


def score(agent, cases):
    """Run every case. Return {"overall": pass rate, "by_category": {cat: pass rate}, "failed": [ids]}."""
    passed, totals, failed = {}, {}, []
    for c in cases:
        ok = grade(c, agent(c["question"]))
        totals[c["category"]] = totals.get(c["category"], 0) + 1
        passed[c["category"]] = passed.get(c["category"], 0) + ok
        if not ok:
            failed.append(c["id"])
    n = len(cases) or 1
    return {"overall": (len(cases) - len(failed)) / n,
            "by_category": {k: passed[k] / totals[k] for k in totals}, "failed": failed}


def should_ship(old, new):
    """Ship the candidate only if the overall score does not drop AND no category drops."""
    if new["overall"] < old["overall"]:
        return False
    return all(new["by_category"].get(k, 0) >= v for k, v in old["by_category"].items())


old, new = score(v1, CASES), score(v2, CASES)
print(f"{len(CASES)} cases")
print("v1:", old)
print("v2:", new)
ship_v2 = should_ship(old, new)
print("Ship v2?", ship_v2)
