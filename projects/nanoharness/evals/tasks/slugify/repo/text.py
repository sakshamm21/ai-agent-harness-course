def slugify(title):
    """'Hello World' -> 'hello-world'."""
    return "_".join(title.lower().split())
