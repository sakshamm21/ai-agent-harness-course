"""Token counting and illustrative prices. ~4 characters per token is the usual rule of thumb."""
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


# Illustrative "sim prices" in $ per million tokens (input, output). Check your provider's pricing page.
PRICES = {
    "small": (1.0, 5.0),    # e.g. a Haiku-class model
    "medium": (3.0, 15.0),  # e.g. a Sonnet-class model
    "large": (15.0, 75.0),  # e.g. an Opus-class model
}


def cost(input_tokens: int, output_tokens: int, tier: str = "medium") -> float:
    pin, pout = PRICES[tier]
    return (input_tokens * pin + output_tokens * pout) / 1_000_000
