# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
schema = get_weather.schema
check("get_weather has a description", len(schema["description"]) >= 20, "Write a docstring that says what it does and when to use it.")
check("city is a required string", schema["input_schema"]["properties"].get("city", {}).get("type") == "string" and "city" in schema["input_schema"]["required"])
check("get_weather('Paris') returns the rain forecast", "rain" in get_weather(city="Paris").lower())
check("unknown cities are handled", "no data" in get_weather(city="Atlantis").lower())
_r = handle(Response(tool_calls=[ToolCall("abc", "get_weather", {"city": "Oslo"})]))
check("handle returns a tool_result with the right id", len(_r) == 1 and _r[0].get("type") == "tool_result" and _r[0].get("tool_use_id") == "abc")
check("the final answer mentions rain", "rain" in final.text.lower())
