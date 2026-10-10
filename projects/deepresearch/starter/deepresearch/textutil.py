"""Small text helpers shared by the corpus, the mock model and the evals."""
from __future__ import annotations

import json
import re

STOPWORDS = set("""
a an the and or but if of to in on at by for with from into onto about as is are was were be been being
it its this that these those there their they them he she his her we our you your i me my
do does did done how what when where which who whom why whose can could would should will shall may might
has have had not no so than then also any all each such very more most much many one per
""".split())

_WORD = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")


def stem(w: str) -> str:
    """A deliberately tiny stemmer: drop a plural or past-tense ending."""
    for suf in ("ies", "es", "s", "ed", "ing"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokenize(text: str) -> list[str]:
    """Lowercase content words, stemmed, stopwords removed. Numbers like 4,000 or 2.0 stay whole."""
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def keywords(text: str) -> str:
    """The content words of a question, as a short search query."""
    seen: list[str] = []
    for w in _WORD.findall(text.lower()):
        if w not in STOPWORDS and w not in seen:
            seen.append(w)
    return " ".join(seen)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def support_score(claim: str, text: str) -> float:
    """Best share of the claim's content words found in any one sentence of `text` (0..1)."""
    words = set(tokenize(claim))
    if not words:
        return 0.0
    best = 0.0
    for s in sentences(text):
        best = max(best, len(words & set(tokenize(s))) / len(words))
    return best


def supports(claim: str, text: str, threshold: float = 0.75) -> bool:
    """A deterministic stand-in for "does this source back this claim?"."""
    return support_score(claim, text) >= threshold


def extract_json(text: str):
    """Pull the first JSON object or array out of a model reply (handles ```json fences and chatter)."""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    while end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            end = text.rfind(closer, start, end)
    return None
