def is_palindrome(text):
    """True if text reads the same backwards, ignoring spaces and case."""
    cleaned = text.replace(" ", "")
    return cleaned == cleaned[::-1]
