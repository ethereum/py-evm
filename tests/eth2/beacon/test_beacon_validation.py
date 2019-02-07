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
    validate_slot,
    validate_epoch_for_current_epoch,
)


@pytest.mark.parametrize(
    "slot,is_valid",
    (
        (tuple(), False),
        ([], False),
        ({}, False),
        (set(), False),
        ('abc', False),
        (1234, True),
        (-1, False),
        (0, True),
        (100, True),
        (2 ** 64, False),
    ),
)
def test_validate_slot(slot, is_valid):
    if is_valid:
        validate_slot(slot)
    else:
        with pytest.raises(ValidationError):
            validate_slot(slot)


@pytest.mark.parametrize(
    (
        'current_epoch, epoch, success'
    ),
    [
        (
            0, 0, True,
        ),
        (
            1, 0, True,
        ),
        (
            2, 0, False,  # epoch < previous_epoch
        ),
        (
            2, 2, True,
        ),
        (
            2, 3, False,  # next_epoch == epoch
        ),
    ]
)
def test_validate_epoch_for_current_epoch(
        current_epoch,
        epoch,
        success,
        epoch_length,
        genesis_epoch):
    if success:
        validate_epoch_for_current_epoch(
            current_epoch=current_epoch,
            given_epoch=epoch,
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length
        )
    else:
        with pytest.raises(ValidationError):
            validate_epoch_for_current_epoch(
                current_epoch=current_epoch,
                given_epoch=epoch,
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length
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
