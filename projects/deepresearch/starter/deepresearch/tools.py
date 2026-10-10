"""The @tool decorator: turns a typed Python function into a tool the model can call."""
from __future__ import annotations

import inspect
import typing
from typing import Any, Callable

_PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


class Tool:
    def __init__(self, fn: Callable, name: str | None = None, description: str | None = None):
        self.fn = fn
        self.name = name or fn.__name__
        self.description = (description or inspect.getdoc(fn) or "").strip()
        self.input_schema = _schema_for(fn)

    @property
    def schema(self) -> dict:
        """The JSON you send to the model in the `tools` list."""
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}

    def __call__(self, **kwargs) -> Any:
        return self.fn(**kwargs)

    def __repr__(self) -> str:
        return f"Tool({self.name})"


def tool(fn: Callable | None = None, *, name: str | None = None, description: str | None = None):
    """Use as @tool or @tool(name=..., description=...)."""
    if fn is None:
        return lambda f: Tool(f, name, description)
    return Tool(fn, name, description)


def _schema_for(fn: Callable) -> dict:
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    props: dict[str, dict] = {}
    required: list[str] = []
    for pname, p in sig.parameters.items():
        t = hints.get(pname, str)
        origin = typing.get_origin(t)
        props[pname] = {"type": _PY_TO_JSON.get(origin or t, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
    return {"type": "object", "properties": props, "required": required}
