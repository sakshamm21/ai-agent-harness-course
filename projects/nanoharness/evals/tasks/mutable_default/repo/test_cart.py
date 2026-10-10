from cart import add_item


def test_separate_carts():
    assert add_item('apple') == ['apple']
    assert add_item('pear') == ['pear']


def test_existing_cart():
    c = ['milk']
    assert add_item('eggs', c) == ['milk', 'eggs']
