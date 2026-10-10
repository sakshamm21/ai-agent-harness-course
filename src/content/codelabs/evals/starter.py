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
CASES = [
    {"id": "r1", "category": "refund", "question": "My headphones from order A-1001 broke. Can I get a refund?",
     "must_include": ["refund", "$89"], "must_not_include": ["can't refund"]},
    {"id": "s1", "category": "order_status", "question": "Where is my order A-1003?",
     "must_include": ["in transit", "thursday"], "must_not_include": []},
    {"id": "c1", "category": "cancel", "question": "Please cancel order A-1004.",
     "must_include": ["cancelled"], "must_not_include": []},
    {"id": "a1", "category": "account", "question": "I forgot my password.",
     "must_include": ["reset password"], "must_not_include": []},
    {"id": "e1", "category": "escalation", "question": "This is a joke. I'm filing a chargeback.",
     "must_include": ["human"], "must_not_include": ["refund"]},
    # TODO: add 15 more cases (20 in total). Cover every category at least 3 times,
    #       and put the risky behaviour in must_not_include (for example a refund
    #       outside the 30-day window: A-1002 and A-1005 were delivered 45 and 31 days ago).
]


def grade(case, answer):
    """True when the answer contains every must_include string and no must_not_include string."""
    # TODO: compare lowercase strings
    return True


def score(agent, cases):
    """Run every case. Return {"overall": pass rate, "by_category": {cat: pass rate}, "failed": [ids]}."""
    # TODO: call agent(case["question"]), grade it, and count passes overall and per category
    return {"overall": 1.0, "by_category": {}, "failed": []}


def should_ship(old, new):
    """Ship the candidate only if the overall score does not drop AND no category drops."""
    # TODO: also compare every category in old["by_category"]
    return new["overall"] >= old["overall"]


old, new = score(v1, CASES), score(v2, CASES)
print(f"{len(CASES)} cases")
print("v1:", old)
print("v2:", new)
ship_v2 = should_ship(old, new)
print("Ship v2?", ship_v2)
