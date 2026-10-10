---
title: "Structured Output"
---

## The scenario

Your accounts team gets eight vendor invoices a day as plain text. You need four fields from each one (`vendor`, `total`, `currency`, `due_date`) as data your code can store. The first version asks the model to "reply with JSON only" and calls `json.loads` on whatever comes back. Press **Run**: half the invoices break it. One reply starts with "Here is the extracted data:", one wraps the JSON in a code fence, one adds a friendly sign-off, and one returns the total as the text `"2,005.00"`.

The fix has three parts: make the model fill in a typed schema (a tool call), check the result in code, and send any errors back once so the model can correct itself.

## Your task

1. Give `record_invoice` real types: `total: float` and `currency: Literal["USD", "EUR", "GBP"]`. The `@tool` decorator turns these types into the JSON schema the model must follow. Print `record_invoice.schema` to see it.
2. Finish `validate(data)`. Return a list of error strings: one for each missing key, a `total` that is not a number, a `currency` outside the three allowed codes, or a `due_date` that is not `YYYY-MM-DD`. An empty list means the invoice is valid.
3. Finish `extract(doc)`. Call `model.complete(messages, tools=[record_invoice.schema])`. The fields arrive in `resp.tool_calls[0].input`, already a Python dict, so there is no text to parse.
4. If `validate` finds problems, append `resp.to_message()` and a `tool_result` block with `"is_error": True` that lists the errors, then call the model again. Retry at most `max_retries` times.

Press **Run** to compare the two failure counts, then **Check**.

## What the checks look for

- The schema types `total` as a number and limits `currency` to USD, EUR or GBP.
- `validate` accepts a good invoice and catches a text total, an unknown currency, a bad date and a missing key.
- The plain-text approach fails on at least 4 of the 8 invoices (your validator catches the text total).
- `extract` returns all 8 invoices valid, including the Northwind one whose date needs a retry.
