from fizz import fizzbuzz


def test_fizzbuzz():
    assert [fizzbuzz(i) for i in (3, 5, 15, 7)] == ['Fizz', 'Buzz', 'FizzBuzz', '7']
