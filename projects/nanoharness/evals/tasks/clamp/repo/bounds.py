def clamp(x, lo, hi):
    """x limited to the range [lo, hi]."""
    return min(lo, max(hi, x))
