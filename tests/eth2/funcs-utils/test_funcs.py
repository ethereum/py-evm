from eth2._utils.funcs import constantly, forever


def test_constantly():
    give_me_two = constantly(2)

    assert 2 == give_me_two()
    assert 2 == give_me_two(1)
    assert 2 == give_me_two(1, 2)
    assert 2 == give_me_two(a=2, b=33)
    assert 2 == give_me_two(1, 2, a=2, b=33)


def test_forever():
    forever_22 = forever(22)

    assert next(forever_22) == 22

    for _, value in zip(range(20), forever_22):
        assert value == 22
