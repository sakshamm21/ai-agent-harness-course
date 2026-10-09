from agentkit_mini import (MCPClient, MCPServer, MockModel, Response, ToolCall, VectorIndex,
                           count_tokens, run_loop, tool)


@tool
def get_weather(city: str) -> str:
    """Gets the current weather for a city. Use for any weather question."""
    return f"18C and cloudy in {city}"


def test_schema():
    s = get_weather.schema
    assert s["name"] == "get_weather"
    assert s["input_schema"]["properties"]["city"]["type"] == "string"
    assert s["input_schema"]["required"] == ["city"]


def test_loop_with_scripted_model():
    model = MockModel([
        Response(tool_calls=[ToolCall("c1", "get_weather", {"city": "Paris"})]),
        Response(text="It is 18C and cloudy in Paris."),
    ])
    r = run_loop(model, [get_weather], "Weather in Paris?")
    assert r.turns == 2 and "18C" in r.final_text
    assert r.messages[2]["content"][0]["type"] == "tool_result"


def test_default_policy_calls_named_tool():
    r = run_loop(MockModel(), [get_weather], "use get_weather for city Lisbon")
    assert r.tool_calls[0]["name"] == "get_weather"
    assert "lisbon" in r.final_text.lower()


def test_pre_tool_blocks():
    model = MockModel([Response(tool_calls=[ToolCall("c1", "get_weather", {"city": "X"})]), Response(text="ok")])
    r = run_loop(model, [get_weather], "hi", pre_tool=lambda n, a: False)
    assert r.messages[2]["content"][0]["is_error"] is True


def test_tool_error_is_reported_not_raised():
    @tool
    def boom() -> str:
        """Always fails."""
        raise ValueError("nope")
    model = MockModel([Response(tool_calls=[ToolCall("c1", "boom", {})]), Response(text="it failed")])
    r = run_loop(model, [boom], "go")
    assert r.tool_calls[0]["error"] and "nope" in r.tool_calls[0]["output"]


def test_max_turns():
    model = MockModel([Response(tool_calls=[ToolCall("c", "get_weather", {"city": "A"})])])
    r = run_loop(model, [get_weather], "loop", max_turns=3)
    assert r.stop_reason == "max_turns" and r.turns == 3


def test_vector_index_synonyms():
    idx = VectorIndex()
    idx.add("How to get your money back for an order", {"id": 1})
    idx.add("Changing the colour theme of the app", {"id": 2})
    assert idx.search("refund please", k=1)[0]["id"] == 1


def test_mcp_roundtrip():
    srv = MCPServer("weather")
    srv.add_tool(get_weather)
    tools = MCPClient(srv).list_tools()
    assert tools[0].name == "get_weather"
    assert "Oslo" in tools[0](city="Oslo")


def test_tokens_and_temperature_variance():
    assert count_tokens("abcd" * 10) == 10
    outs = {MockModel([Response(text="a good quick happy big answer")], seed=s).complete([{"role": "user", "content": "x"}], temperature=1).text for s in range(8)}
    assert len(outs) > 1
    zero = {MockModel([Response(text="a good answer")], seed=s).complete([{"role": "user", "content": "x"}], temperature=0).text for s in range(5)}
    assert len(zero) == 1
