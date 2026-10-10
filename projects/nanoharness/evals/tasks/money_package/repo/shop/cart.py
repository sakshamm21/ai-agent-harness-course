from shop.money import to_cents


def total_cents(prices):
    return sum(to_cents(p) for p in prices)
