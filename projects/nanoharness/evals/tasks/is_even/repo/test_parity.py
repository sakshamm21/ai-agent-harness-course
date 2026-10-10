from parity import is_even, evens


def test_is_even():
    assert is_even(4) and not is_even(7)


def test_evens():
    assert evens([1, 2, 3, 4]) == [2, 4]
