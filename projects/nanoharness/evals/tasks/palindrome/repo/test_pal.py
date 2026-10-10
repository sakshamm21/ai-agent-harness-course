from pal import is_palindrome


def test_pal():
    assert is_palindrome('Never odd or even')
    assert not is_palindrome('agent')
