from evm.utils.functional import compose


def test_composition_no_functions():
    fn = compose()
    assert fn(5) == 5


def test_composition_single_function():
    def fn(x):
        return x * 2

    assert compose(fn)(5) == 10


def test_composition_multiple_function():
    def fn(x):
        return x + 1

    assert compose(fn, fn, fn)(5) == 8


def test_composition_retains_ordering():
    def fn_a(x):
        return x + 'a'

    def fn_b(x):
        return x + 'b'

    def fn_c(x):
        return x + 'c'

    assert compose(fn_a, fn_b, fn_c)('123') == '123abc'
