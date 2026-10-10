from calendar_util import is_leap


def test_leap():
    assert is_leap(2024) and is_leap(2000)
    assert not is_leap(1900) and not is_leap(2023)
