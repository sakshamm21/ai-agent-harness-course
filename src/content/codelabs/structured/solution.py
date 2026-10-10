import json
import re
from typing import Literal
from agentkit_mini import MockModel, Response, ToolCall, tool, get_model

INVOICES = [
    "Acme Paper Co. Invoice 1001. Total due: $1,240.00 USD by 2026-11-03.",
    "Brightline Ltd. Invoice B-77. Amount: EUR 310.50. Due 2026-10-28.",
    "Kestrel Freight. Invoice KF-9. Please pay GBP 89.99 before 2026-11-15.",
    "Acme Paper Co. Invoice 1002. Total due: $56.10 USD by 2026-11-10.",
    "Northwind Supply. Invoice 554. Total EUR 2,005.00, due 3 November 2026.",
    "Orbit Cloud. Invoice OC-12. Monthly fee $499.00 USD, due 2026-11-01.",
    "Kestrel Freight. Invoice KF-10. Please pay GBP 120.00 before 2026-11-20.",
    "Brightline Ltd. Invoice B-78. Amount: EUR 42.00. Due 2026-11-02.",
]

# --- The scripted model (offline). Do not edit; it behaves like a real model on a bad day. ---
_TRUTH = [("Acme Paper Co.", 1240.00, "USD", "2026-11-03"), ("Brightline Ltd.", 310.50, "EUR", "2026-10-28"),
          ("Kestrel Freight", 89.99, "GBP", "2026-11-15"), ("Acme Paper Co.", 56.10, "USD", "2026-11-10"),
          ("Northwind Supply", 2005.00, "EUR", "2026-11-03"), ("Orbit Cloud", 499.00, "USD", "2026-11-01"),
          ("Kestrel Freight", 120.00, "GBP", "2026-11-20"), ("Brightline Ltd.", 42.00, "EUR", "2026-11-02")]


def _script(messages, tools):
    first = messages[0]["content"]
    i = next(k for k, doc in enumerate(INVOICES) if doc in first)
    vendor, total, currency, due = _TRUTH[i]
    data = {"vendor": vendor, "total": total, "currency": currency, "due_date": due}
    if tools:  # schema-constrained: the arguments always match the schema's types
        retried = len(messages) > 1
        if i == 4 and not retried:
            data["due_date"] = "3 November 2026"  # a string, so the schema allows it
        return Response(tool_calls=[ToolCall(f"call_{i}", "record_invoice", data)])
    js = json.dumps(data)
    if i == 1:
        return Response(text="Here is the extracted data:\n" + js)
    if i == 3:
        return Response(text="```json\n" + js + "\n```")
    if i == 4:
        return Response(text=json.dumps({**data, "total": "2,005.00", "due_date": "3 November 2026"}))
    if i == 6:
        return Response(text=js + "\nLet me know if you need anything else!")
    return Response(text=js)


model = get_model(MockModel(_script))
# --- End of the scripted model. ---

PROMPT = "Extract the vendor, total, currency and due date from this invoice:\n\n"


def naive_extract(doc):
    """Ask for JSON in plain text and hope."""
    resp = model.complete([{"role": "user", "content": PROMPT + doc + "\n\nReply with JSON only."}])
    return json.loads(resp.text)


@tool
def record_invoice(vendor: str, total: float, currency: Literal["USD", "EUR", "GBP"], due_date: str) -> str:
    """Records the fields extracted from one invoice. Use it once per invoice. due_date must be YYYY-MM-DD."""
    return "recorded"


def validate(data):
    """Return a list of problems with an extracted invoice. Empty list = valid."""
    errors = []
    for key in ["vendor", "total", "currency", "due_date"]:
        if key not in data:
            errors.append(f"missing {key}")
    if "total" in data and not isinstance(data["total"], (int, float)):
        errors.append("total must be a number, not text")
    if "currency" in data and data["currency"] not in ("USD", "EUR", "GBP"):
        errors.append("currency must be USD, EUR or GBP")
    if "due_date" in data and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data["due_date"])):
        errors.append("due_date must be YYYY-MM-DD")
    return errors


def extract(doc, max_retries=1):
    """Ask for a record_invoice tool call, validate it, and retry once with the errors."""
    messages = [{"role": "user", "content": PROMPT + doc}]
    for attempt in range(max_retries + 1):
        resp = model.complete(messages, tools=[record_invoice.schema])
        if not resp.tool_calls:
            return {}
        call = resp.tool_calls[0]
        errors = validate(call.input)
        if not errors:
            return call.input
        messages.append(resp.to_message())
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id,
                                                      "content": "Invalid: " + "; ".join(errors), "is_error": True}]})
    return call.input


naive_failures = 0
for doc in INVOICES:
    try:
        if validate(naive_extract(doc)):
            naive_failures += 1
    except json.JSONDecodeError:
        naive_failures += 1

results = [extract(doc) for doc in INVOICES]
structured_failures = sum(1 for r in results if validate(r))
print(f"Plain-text JSON: {naive_failures}/{len(INVOICES)} failed")
print(f"Tool + validation + retry: {structured_failures}/{len(INVOICES)} failed")
for r in results[:3]:
    print(r)
