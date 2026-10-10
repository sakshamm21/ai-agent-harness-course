from listutil import first_n


def test_first_two():
    assert first_n([1, 2, 3], 2) == [1, 2]


def test_zero():
    assert first_n([1, 2, 3], 0) == []
