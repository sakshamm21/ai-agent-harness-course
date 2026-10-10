import random
from agentkit_mini import MockModel, Response, get_model

# A toy language model: for each token, the probabilities of the next token.
# A real LLM computes a table like this over ~100,000 tokens, fresh, at every step.
NEXT = {
    "<start>": {"The": 0.7, "A": 0.3},
    "The": {"cat": 0.5, "dog": 0.3, "model": 0.2},
    "A": {"cat": 0.6, "dog": 0.4},
    "cat": {"sat": 0.6, "slept": 0.3, "sang": 0.1},
    "dog": {"barked": 0.7, "sat": 0.3},
    "model": {"predicted": 0.8, "sat": 0.2},
    "sat": {".": 1.0}, "slept": {".": 1.0}, "sang": {".": 1.0},
    "barked": {".": 1.0}, "predicted": {".": 1.0},
}


def apply_temperature(probs, t):
    """Reshape a next-token distribution. t=0: always the top token. t=1: unchanged."""
    if t == 0:
        top = max(probs, key=probs.get)
        return {tok: (1.0 if tok == top else 0.0) for tok in probs}
    scaled = {tok: p ** (1 / t) for tok, p in probs.items()}
    total = sum(scaled.values())
    return {tok: v / total for tok, v in scaled.items()}


def sample(probs, rng):
    """Pick one token at random, weighted by its probability."""
    r, acc = rng.random(), 0.0
    for tok, p in probs.items():
        acc += p
        if r < acc:
            return tok
    return tok


def generate(t, rng, max_tokens=8):
    """Generate one sentence, one token at a time, until '.' or max_tokens."""
    tokens = []
    prev = "<start>"
    for _ in range(max_tokens):
        nxt = sample(apply_temperature(NEXT[prev], t), rng)
        tokens.append(nxt)
        if nxt == ".":
            break
        prev = nxt
    return " ".join(tokens)


print("t=0  :", [generate(0, random.Random(s)) for s in range(3)])
print("t=1.0:", [generate(1.0, random.Random(s)) for s in range(3)])

# Streaming: a real model sends its answer as a stream of small text pieces.
mock = MockModel([Response(text="A small cat sat on a big mat and looked happy.")], seed=1)
model = get_model(mock)
pieces = []
for event in model.stream([{"role": "user", "content": "Describe a cat in one sentence."}], temperature=1.0):
    if event["type"] == "text_delta":
        pieces.append(event["text"])
        print(repr(event["text"]), end=" ")
    elif event["type"] == "done":
        final = event["response"]
print("\nFull text:", "".join(pieces))
