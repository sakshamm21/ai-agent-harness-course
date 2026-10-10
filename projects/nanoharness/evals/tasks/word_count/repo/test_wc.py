from wc import count_words


def test_counts():
    assert count_words('a b a A') == {'a': 3, 'b': 1}
