from text import slugify


def test_slugify():
    assert slugify('Hello World') == 'hello-world'
    assert slugify('  Agent   Harness ') == 'agent-harness'
