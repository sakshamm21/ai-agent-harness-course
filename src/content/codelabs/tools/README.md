---
title: "Function Calling"
---

## The scenario

A user asks: **"Do I need an umbrella in Paris today?"** The model can't know the weather. Your job is to give it a tool and handle the call.

## Your task

1. Finish `get_weather(city)` so it returns the fake weather from `WEATHER` (for example `"Paris: 14C, light rain"`). For an unknown city, return `"No data for <city>"`.
2. Write a one-line docstring for it. The `@tool` decorator turns the docstring into the description the model reads.
3. In `handle(resp)`, run each tool call the model asked for and return a list of `tool_result` blocks.

Press **Run** to see what happens, then **Check**.

## What the checks look for

- `get_weather` has a description that says what it does.
- The tool's schema has a required `city` string parameter.
- `handle` runs the call and returns a `tool_result` with the matching `tool_use_id`.
- The final answer mentions rain.
