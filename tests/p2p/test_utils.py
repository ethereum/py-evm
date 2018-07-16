from hypothesis import (
    given,
    strategies as st,
)

import pytest

from eth.exceptions import ValidationError
from p2p.utils import get_scaled_batches


@given(
    st.lists(st.floats(min_value=0), min_size=1),
    # doesn't matter what the source element type is, picked text (mostly) arbitrarily:
    st.lists(elements=st.text(), unique=True),
)
def test_scaled_batches_are_complete(scales_list, source):
    scales = tuple(scales_list)
    batches = get_scaled_batches(scales, source)

    # the batches must be the same length as the scaled workers
    assert len(scales) == len(batches)

    # the total number of elements returned must be equal to the length of the source
    assert sum(map(len, batches)) == len(source)

    # all the elements must be found in the batches
    batched_set = set(el for batch in batches for el in batch)
    assert batched_set == set(source)

    # there must be no duplicates
    batched_tuple = tuple(el for batch in batches for el in batch)
    assert len(batched_tuple) == len(batched_set)


def test_scaled_batches_empty():
    with pytest.raises(ValidationError):
        get_scaled_batches(tuple(), ['has source data'])


def test_scaled_batches_nan():
    with pytest.raises(ValidationError):
        get_scaled_batches(tuple([1.2, float('nan')]), ['has source data'])
