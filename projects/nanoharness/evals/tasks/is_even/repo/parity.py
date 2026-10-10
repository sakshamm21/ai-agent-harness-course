def is_even(n):
    return n % 2 == 1


def evens(xs):
    return [x for x in xs if is_even(x)]
