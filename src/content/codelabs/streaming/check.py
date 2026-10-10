# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
_m = status_line({"type": "model", "turn": 1, "text": "", "tool_calls": ["lookup_order"]})
check("status line for a tool request names the tool", isinstance(_m, str) and "lookup_order" in _m,
      'For a "model" event with tool_calls, return something like "Looking up: lookup_order...".')
_t = status_line({"type": "tool", "turn": 1, "name": "get_tracking", "input": {}, "output": "ok"})
check("status line for a finished tool names it", isinstance(_t, str) and "get_tracking" in _t)
_e = status_line({"type": "tool_error", "turn": 2, "name": "get_tracking", "input": {}, "output": "boom"})
check("status line for a failed tool says it failed", isinstance(_e, str) and "fail" in _e.lower() and "get_tracking" in _e)
_d = status_line({"type": "done", "turn": 3, "text": "..."})
check("status line for done gives the turn count", isinstance(_d, str) and "3" in _d)

_chunks = [c for kind, c in TIMELINE if kind == "text"]
check("the answer arrived in many small chunks", len(_chunks) >= 20,
      "In Streaming.complete, loop over self.inner.stream(...) and append each text_delta to TIMELINE.")
check("the full answer was shown on screen", result.final_text and result.final_text in "".join(_chunks),
      "Append every text_delta chunk; together they must spell out the final answer.")
_kinds = [kind for kind, _ in TIMELINE]
_first_status = _kinds.index("status") if "status" in _kinds else -1
check("text and status lines are interleaved", _first_status > 0 and "text" in _kinds[:_first_status] and "text" in _kinds[_first_status:],
      "The user should see the first words before the tool status lines, and more words after them.")
check("Stop ends the run with the partial text", stopped.final_text.endswith("[stopped]"),
      'When self.shown reaches self.stop_after, return Response(text=text.rstrip() + " [stopped]").')
check("Stop prevents the next tool call", stopped.turns == 2 and all(c["name"] != "get_tracking" for c in stopped.tool_calls),
      "Return a Response with no tool_calls when stopping, so run_loop treats it as the final answer.")
