from agentkit_mini import MockModel, Response, ToolCall, tool, get_model

WEATHER = {"paris": "14C, light rain", "cairo": "31C, sunny", "oslo": "3C, snow"}


@tool
def get_weather(city: str) -> str:
    # TODO: add a docstring, then look the city up in WEATHER (lowercase)
    return "TODO"


def handle(resp):
    """Run every tool call in the model's response. Return a list of tool_result blocks."""
    results = []
    # TODO: for each call in resp.tool_calls, run get_weather(**call.input) and append
    # {"type": "tool_result", "tool_use_id": call.id, "content": <output>}
    return results


# A scripted model: first it asks for the tool, then it answers using the result.
mock = MockModel(lambda messages, tools: (
    Response(tool_calls=[ToolCall("call_1", "get_weather", {"city": "Paris"})])
    if len(messages) == 1 else
    Response(text=f"The forecast says: {(messages[-1]['content'] or [{'content': 'no tool result'}])[0]['content']}. Bring an umbrella if it mentions rain.")
))
model = get_model(mock)

messages = [{"role": "user", "content": "Do I need an umbrella in Paris today?"}]
resp = model.complete(messages, tools=[get_weather.schema])
print("Model asked for:", [(c.name, c.input) for c in resp.tool_calls])
messages.append(resp.to_message())
messages.append({"role": "user", "content": handle(resp)})
final = model.complete(messages, tools=[get_weather.schema])
print("Final answer:", final.text)
