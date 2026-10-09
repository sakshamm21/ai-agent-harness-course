"""Token counting. Real tokenizers vary; ~4 characters per token is the usual rule of thumb."""
from __future__ import annotations

import json


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def count_message_tokens(message: dict) -> int:
    c = message.get("content", "")
    if isinstance(c, str):
        return count_tokens(c) + 4
    return sum(count_tokens(json.dumps(b)) for b in c) + 4


def count_context(messages: list[dict], system: str = "", tools: list[dict] | None = None) -> int:
    return (count_tokens(system) + sum(count_message_tokens(m) for m in messages)
            + sum(count_tokens(json.dumps(t)) for t in tools or []))


# Illustrative prices in $ per million tokens (input, output). Check your provider's pricing page.
PRICES = {
    "small": (1.0, 5.0),
    "medium": (3.0, 15.0),
    "large": (15.0, 75.0),
}


def cost(input_tokens: int, output_tokens: int, tier: str = "medium") -> float:
    pin, pout = PRICES[tier]
    return (input_tokens * pin + output_tokens * pout) / 1_000_000
