from agentkit_mini import Model, MockModel, Response, ToolCall, tool, run_loop, get_model

ORDERS = {"4417": "shipped with DHL, tracking JD0142"}
SCANS = {"JD0142": "Arrived at Leipzig hub, out for delivery tomorrow"}


@tool
def lookup_order(order_id: str) -> str:
    """Gets an order's status by order id. Use it for any question about an order."""
    return ORDERS.get(order_id, f"No order {order_id}")


@tool
def get_tracking(tracking_id: str) -> str:
    """Gets the latest carrier scan for a tracking number."""
    return SCANS.get(tracking_id, f"No scans for {tracking_id}")


TIMELINE = []  # what the user sees, in order: ("text", chunk) or ("status", line)


def status_line(event):
    """Turn one loop event into a short status line, or None to show nothing."""
    if event["type"] == "model" and event["tool_calls"]:
        return "Looking up: " + ", ".join(event["tool_calls"]) + "..."
    if event["type"] == "tool":
        return f"✓ {event['name']}"
    if event["type"] == "tool_error":
        return f"✗ {event['name']} failed"
    if event["type"] == "done":
        return f"Answer ready ({event['turn']} turns)"
    return None


def on_event(event):
    line = status_line(event)
    if line:
        after_text = bool(TIMELINE) and TIMELINE[-1][0] == "text"
        TIMELINE.append(("status", line))
        print(("\n" if after_text else "") + f"  [{line}]")


class Streaming(Model):
    """Wraps a model so every call streams its text to the screen as it arrives."""

    def __init__(self, inner, stop_after=None):
        self.inner, self.stop_after, self.shown = inner, stop_after, 0

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
        text = ""
        for ev in self.inner.stream(messages, tools=tools, system=system, temperature=temperature):
            if ev["type"] == "text_delta":
                text += ev["text"]
                self.shown += 1
                TIMELINE.append(("text", ev["text"]))
                print(ev["text"], end="")
                if self.stop_after is not None and self.shown >= self.stop_after:
                    return Response(text=text.rstrip() + " [stopped]")  # no tool calls: the loop ends
            elif ev["type"] == "done":
                return ev["response"]
        return Response(text=text)


def script(messages, tools):
    if len(messages) == 1:
        return Response(text="Let me check that order.", tool_calls=[ToolCall("c1", "lookup_order", {"order_id": "4417"})])
    if len(messages) == 3:
        return Response(text="It shipped with DHL. Checking the latest scan now.", tool_calls=[ToolCall("c2", "get_tracking", {"tracking_id": "JD0142"})])
    return Response(text="Your order 4417 shipped with DHL. The last scan shows it arrived at the Leipzig hub, "
                         "and it is out for delivery tomorrow. Your tracking number is JD0142.")


TOOLS = [lookup_order, get_tracking]
ASK = "Where is my order 4417?"

result = run_loop(Streaming(get_model(MockModel(script))), TOOLS, ASK, on_event=on_event)
print("\n\nChunks streamed:", sum(1 for kind, _ in TIMELINE if kind == "text"))

print("\n--- The user presses Stop after 12 words ---")
stopped = run_loop(Streaming(get_model(MockModel(script)), stop_after=12), TOOLS, ASK, on_event=on_event)
print("\nFinal text:", stopped.final_text)
