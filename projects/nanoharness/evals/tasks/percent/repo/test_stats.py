from stats import percent


def test_percent():
    assert percent(1, 4) == 25.0
    assert percent(3, 3) == 100.0
