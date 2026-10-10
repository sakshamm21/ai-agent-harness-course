from board import top_scores


def test_top():
    assert top_scores([5, 1, 9, 7], 2) == [9, 7]
