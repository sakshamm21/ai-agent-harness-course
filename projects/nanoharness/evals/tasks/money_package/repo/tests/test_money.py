from shop.cart import total_cents
from shop.money import to_cents


def test_to_cents():
    assert to_cents(1.25) == 125


def test_total():
    assert total_cents([1.25, 0.5]) == 175
