# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
_props = record_invoice.schema["input_schema"]["properties"]
check("total is a number in the schema", _props.get("total", {}).get("type") == "number",
      "Annotate the parameter as total: float.")
check("currency is limited to USD, EUR, GBP", sorted(_props.get("currency", {}).get("enum", [])) == ["EUR", "GBP", "USD"],
      'Annotate it as currency: Literal["USD", "EUR", "GBP"].')
_good = {"vendor": "Acme", "total": 12.5, "currency": "USD", "due_date": "2026-11-03"}
check("validate accepts a good invoice", validate(_good) == [], "A complete, well-typed invoice should give an empty list.")
check("validate rejects a total written as text", len(validate({**_good, "total": "2,005.00"})) > 0,
      "Check isinstance(data['total'], (int, float)).")
check("validate rejects an unknown currency", len(validate({**_good, "currency": "dollars"})) > 0)
check("validate rejects a date that is not YYYY-MM-DD", len(validate({**_good, "due_date": "3 November 2026"})) > 0,
      'Use re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", str(data["due_date"])).')
_missing = dict(_good); del _missing["vendor"]
check("validate reports a missing key", len(validate(_missing)) > 0)
check("plain-text JSON fails on at least 4 of 8 invoices", naive_failures >= 4,
      "Three replies are not valid JSON at all; the fourth has a text total that your validator should catch.")
check("extract returns all 8 invoices valid", len(results) == 8 and all(r and not validate(r) for r in results),
      "Call the model with tools=[record_invoice.schema], validate the tool call's input, and retry once with the errors.")
_nw = extract(INVOICES[4])
check("the Northwind date was fixed by the retry", _nw.get("due_date") == "2026-11-03",
      "The first answer has due_date '3 November 2026'. Send the validation errors back as an is_error tool_result and ask again.")
