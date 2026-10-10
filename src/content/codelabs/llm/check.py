# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
import random as _random

_p = {"cat": 0.5, "dog": 0.3, "model": 0.2}
_t0 = apply_temperature(_p, 0)
check("t=0 puts all probability on the top token", abs(_t0.get("cat", 0) - 1.0) < 1e-9 and _t0.get("dog", 1) == 0,
      "When t == 0, return 1.0 for the most likely token and 0.0 for every other token.")
_t1 = apply_temperature(_p, 1.0)
check("t=1 leaves the probabilities unchanged", all(abs(_t1[k] - _p[k]) < 1e-9 for k in _p))
_half = apply_temperature(_p, 0.5)
check("t=0.5 sharpens the distribution and still sums to 1",
      abs(sum(_half.values()) - 1) < 1e-9 and _half["cat"] > 0.6,
      "Raise each probability to the power 1/t (here 2), then divide each by the total.")
_cold = {generate(0, _random.Random(s)) for s in range(10)}
check("generate at t=0 always gives the same sentence", len(_cold) == 1 and next(iter(_cold)).endswith("."),
      "Loop: sample the next token, append it, stop at '.', otherwise set prev to it.")
_hot = {generate(1.0, _random.Random(s)) for s in range(20)}
check("generate at t=1 gives several different sentences", len(_hot) >= 3)
check("the stream arrived in several pieces", len(pieces) > 3, "Append event['text'] for every text_delta event.")
_final = globals().get("final")
check("the pieces join up to the final answer", _final is not None and "".join(pieces) == _final.text,
      "Keep event['response'] from the done event in a variable called final.")
