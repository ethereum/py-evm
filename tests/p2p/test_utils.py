from hypothesis import (
    given,
    strategies as st,
)

import pytest

from eth.exceptions import ValidationError
from p2p.utils import get_scaled_batches


@given(
    # doesn't matter what the worker type is, picked binary (mostly) arbitrarily:
    st.dictionaries(keys=st.binary(), values=st.floats(min_value=0), min_size=1),
    # doesn't matter what the source element type is, picked text (mostly) arbitrarily:
    st.lists(elements=st.text(), unique=True),
)
def test_scaled_batches_are_complete(scaled_workers, source):
    batches = get_scaled_batches(scaled_workers, source)

    # every resulting worker must be in the input workers set
    assert all(worker in scaled_workers for worker in batches.keys())

    # no batches may be empty
    assert all(len(batch) > 0 for batch in batches.values())

    # the total number of elements returned must be equal to the length of the source
    assert sum(map(len, batches.values())) == len(source)

    # all the elements must be found in the batches
    batched_set = set(el for batch in batches.values() for el in batch)
    assert batched_set == set(source)

    # there must be no duplicates
    batched_tuple = tuple(el for batch in batches.values() for el in batch)
    assert len(batched_tuple) == len(batched_set)


@pytest.mark.parametrize(
    'scaled_workers, source, expected_batch_sizes',
    (
        ({b'slow': 1.5, b'fast': 1.6}, ['job-a'], {b'fast': 1}),
        ({b'slow': 1.5, b'fast': 1.6}, ['job-a', 'job-b'], {b'fast': 2}),
        ({b'slow': 1.0, b'fast': 1.9}, ['A', 'B', 'C'], {b'slow': 1, b'fast': 2}),
    ),
)
def test_scaled_batches(scaled_workers, source, expected_batch_sizes):
    batches = get_scaled_batches(scaled_workers, source)
    batch_sizes = {worker: len(batch) for worker, batch in batches.items()}
    assert batch_sizes == expected_batch_sizes


def test_scaled_batches_empty():
    with pytest.raises(ValidationError):
        get_scaled_batches({}, ['has source data'])


def test_scaled_batches_nan():
    with pytest.raises(ValidationError):
        get_scaled_batches({b'a': 1.2, b'b': float('nan')}, ['has source data'])
