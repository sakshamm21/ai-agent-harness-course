"""agentkit_mini: the small agent toolkit used by the Free Agent Harness code labs.

Everything runs offline with MockModel. Swap in AnthropicModel(api_key) for real calls.
"""
from .model import AnthropicModel, MockModel, Model, Response, ToolCall, Usage
from .tools import Tool, tool, to_schemas
from .loop import RunResult, run_loop
from .tokens import cost, count_context, count_message_tokens, count_tokens, PRICES
from .embed import VectorIndex, cosine, embed
from .mcp import MCPClient, MCPServer

__all__ = [
    "AnthropicModel", "MockModel", "Model", "Response", "ToolCall", "Usage",
    "Tool", "tool", "to_schemas", "RunResult", "run_loop",
    "cost", "count_context", "count_message_tokens", "count_tokens", "PRICES",
    "VectorIndex", "cosine", "embed", "MCPClient", "MCPServer",
]
__version__ = "0.1.0"


def get_model(mock: "Model | None" = None, model: str = "claude-sonnet-5-5") -> "Model":
    """The lab's model: AnthropicModel when the learner switched on a real key, else the given mock.

    Set FAH_REAL_MODEL=1 and ANTHROPIC_API_KEY to use the real API (the site's toggle does this).
    """
    import os
    if os.environ.get("FAH_REAL_MODEL") == "1" and os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicModel(os.environ["ANTHROPIC_API_KEY"], model=model)
    return mock if mock is not None else MockModel()


__all__.append("get_model")
