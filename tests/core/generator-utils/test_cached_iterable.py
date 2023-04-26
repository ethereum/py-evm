import itertools

from eth_utils.toolz import (
    first,
    nth,
)

from eth._utils.generator import (
    CachedIterable,
)


def test_cached_generator():
    use_once = itertools.count()
    repeated_use = CachedIterable(use_once)

    for find_val in [1, 0, 10, 5]:
        assert find_val == nth(find_val, repeated_use)


def test_laziness():
    def crash_after_first_val():
        yield 1
        raise Exception("oops, iterated past first value")

    repeated_use = CachedIterable(crash_after_first_val())
    assert first(repeated_use) == 1
    assert first(repeated_use) == 1


def test_cached_generator_iterable():
    input_vals = [2]
    repeated_use = CachedIterable(input_vals)
    assert list(repeated_use) == input_vals
    assert list(repeated_use) == input_vals
