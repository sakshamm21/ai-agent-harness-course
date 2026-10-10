"""deepresearch: a multi-agent research assistant over an offline corpus.

    from deepresearch import research
    print(research("When did the Velmora Tunnel open?").report)

Runs on a deterministic mock model unless ANTHROPIC_API_KEY is set.
"""
from .corpus import Corpus, Doc
from .model import AnthropicModel, MockModel, Model, ResearchMock, Response, ToolCall, Usage, get_models
from .records import Claim, ResearchResult, WorkerResult
from .research import research

__all__ = ["Corpus", "Doc", "AnthropicModel", "MockModel", "Model", "ResearchMock", "Response", "ToolCall",
           "Usage", "get_models", "Claim", "ResearchResult", "WorkerResult", "research"]
__version__ = "0.1.0"
