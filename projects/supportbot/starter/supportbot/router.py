"""Part 4: route each message to one of four lanes with a small, fast model.

The route decides two things downstream: which system prompt the agent gets and,
more importantly, which tools it is allowed to see.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import ROUTER_MARK, ROUTES, Model

ROUTER_SYSTEM = f"""{ROUTER_MARK} for Northwind Outfitters, an outdoor gear store.
Read the customer's message and reply with exactly one label:
refund            the customer wants money back for an order
order_status      where an order is, when it arrives, what its status means
product_question  a question the help center answers: products, sizing, returns policy, shipping, payments, accounts
other             asks for a person, a complaint, small talk, or anything else
Reply with the label only, no punctuation."""

# Least privilege: each lane sees only the tools it needs.
TOOLS_BY_ROUTE = {
    "refund": ["lookup_order", "issue_refund", "escalate_to_human"],
    "order_status": ["lookup_order", "escalate_to_human"],
    "product_question": ["escalate_to_human"],
    "other": ["escalate_to_human"],
}

# Fallback rules, checked top to bottom. Used when the model's reply is not a label.
RULES = [
    ("other", r"\b(human|real person|manager|supervisor|complain|complaint|speak to|talk to)\b"),
    ("refund", r"\b(refunds?|money back|reimburse)\b"),
    ("order_status", r"\b(NW-\d{4}|where is my|track|tracking|my order|my package|shipped yet)\b"),
    ("product_question", r"\?|\b(how|what|can i|do you|does)\b"),
]


@dataclass
class Route:
    label: str
    source: str        # "model" or "rules"
    raw: str = ""      # what the model actually said


def rule_route(text: str) -> str:
    """Keyword routing: first matching rule wins, otherwise "other"."""
    raise NotImplementedError("Part 4: route with keyword rules (rule_route)")


def parse_label(text: str) -> str | None:
    """Accept "refund", " Refund.", "order status"; reject anything that is not exactly one label."""
    raise NotImplementedError("Part 4: parse the router's label (parse_label)")


def route(text: str, model: Model | None = None) -> Route:
    """Ask the router model; fall back to rules if there is no model or its answer is not a label."""
    raise NotImplementedError("Part 4: route with the small model (route)")


def routing_text(message: str, previous_user_messages: list[str]) -> str:
    """A bare follow-up like "It's NW-1004" has no intent of its own: route it with the turn before."""
    if previous_user_messages and len(message.split()) <= 4:
        return previous_user_messages[-1] + "\n" + message
    return message
