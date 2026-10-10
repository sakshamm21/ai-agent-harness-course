from words import reverse_words


def test_reverse():
    assert reverse_words('hello big world') == 'world big hello'
