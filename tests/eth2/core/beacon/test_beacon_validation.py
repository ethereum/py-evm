import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils import (
    ValidationError,
)

from eth2._utils.bitfield import (
    get_bitfield_length,
    get_empty_bitfield,
    set_voted,
)
from eth2.beacon.validation import (
    validate_bitfield,
)


@pytest.mark.parametrize(
    (
        'is_valid'
    ),
    [
        (True),
        (False),
    ]
)
@given(committee_size=st.integers(0, 1000))
def test_validate_bitfield_bitfield_length(committee_size, is_valid):
    if is_valid:
        testing_committee_size = committee_size
    else:
        testing_committee_size = committee_size + 1

    bitfield = get_empty_bitfield(testing_committee_size)

    if not is_valid and len(bitfield) != get_bitfield_length(committee_size):
        with pytest.raises(ValidationError):
            validate_bitfield(bitfield, committee_size)
    else:
        validate_bitfield(bitfield, committee_size)


@given(committee_size=st.integers(0, 1000))
def test_validate_bitfield_padding_zero(committee_size):

    bitfield = get_empty_bitfield(committee_size)
    for index in range(committee_size):
        bitfield = set_voted(bitfield, index)

    if committee_size % 8 != 0:
        bitfield = set_voted(bitfield, committee_size)
        with pytest.raises(ValidationError):
            validate_bitfield(bitfield, committee_size)
    else:
        validate_bitfield(bitfield, committee_size)
