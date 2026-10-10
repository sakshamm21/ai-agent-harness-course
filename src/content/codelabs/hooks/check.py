# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
check("pre_tool blocks a write to .env", pre_tool("write_file", {"path": ".env", "content": "x"}) is False,
      "Return False (not None) from pre_tool when name is write_file and the file name is .env.")
check("pre_tool blocks .env.local in a subfolder", pre_tool("write_file", {"path": "config/.env.local", "content": "x"}) is False,
      "Look at the last part of the path: path.split('/')[-1]. Block it when it is .env or starts with .env.")
check("pre_tool lets ordinary writes through", pre_tool("write_file", {"path": "docs/environment.md", "content": "x"}) is not False
      and pre_tool("write_file", {"path": "src/envelope.py", "content": "x"}) is not False,
      "Match the file name exactly; 'environment.md' contains 'env' but is not a secrets file.")
check("the live key in .env survived the run", FILES.get(".env") == "STRIPE_KEY=sk_live_51H8xQ2",
      "The model's first call overwrote .env. Your pre_tool hook should have blocked it.")
check("config/.env.local was never written", "config/.env.local" not in FILES)
check("the docs file was still written", "docs/environment.md" in FILES, "Only secrets files should be blocked.")
check("app.py was auto-formatted after the edit", FILES.get("app.py") == "def total(xs):\n    return sum(xs)\n",
      "In post_tool, when name is write_file and the path ends with .py, set FILES[path] = fmt(FILES[path]).")
FILES["x.py"] = "a\t"
_r = post_tool("write_file", {"path": "x.py", "content": "a\t"}, "Wrote 2 chars to x.py")
check("post_tool tells the model it formatted the file", isinstance(_r, str) and "format" in _r.lower(),
      "Return the original result plus ' (auto-formatted)' so the next turn sees what changed.")
FILES.pop("x.py", None)
check("post_tool leaves other tools alone", post_tool("read_file", {"path": "app.py"}, "text") is None)
check("the model was told about the blocked writes",
      sum(1 for m in result.messages if m["role"] == "user" and isinstance(m["content"], list)
          for b in m["content"] if b.get("is_error")) == 2,
      "run_loop turns a False from pre_tool into an error tool_result. Two writes should have been blocked.")
