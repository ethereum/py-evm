import pytest

from eth_utils import (
    ValidationError,
)

from eth.beacon.state_machines.validation import (
    validate_attestation_slot,
    validate_attestation_justified_block_root,
    validate_attestation_justified_slot,
)
from eth.beacon.types.attestation_data import (
    AttestationData,
)


@pytest.mark.parametrize(
    (
        'attestation_slot,current_slot,epoch_length,'
        'min_attestation_inclusion_delay,is_valid'
    ),
    [
        (0, 5, 5, 1, True),
        (0, 5, 5, 5, True),
        (0, 5, 5, 6, False),  # not past min inclusion delay
        (7, 5, 10, 1, False),  # attestation slot in future
        (10, 20, 10, 2, True),
        (9, 20, 10, 2, False),  # more than epoch_length slots have past
    ]
)
def test_validate_attestation_slot(sample_attestation_data_params,
                                   attestation_slot,
                                   current_slot,
                                   epoch_length,
                                   min_attestation_inclusion_delay,
                                   is_valid):
    sample_attestation_data_params['slot'] = attestation_slot
    attestation_data = AttestationData(**sample_attestation_data_params)

    if is_valid:
        validate_attestation_slot(
            attestation_data,
            current_slot,
            epoch_length,
            min_attestation_inclusion_delay,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_slot(
                attestation_data,
                current_slot,
                epoch_length,
                min_attestation_inclusion_delay,
            )


@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'attestation_justified_slot,'
        'current_slot,'
        'previous_justified_slot,'
        'justified_slot,'
        'epoch_length,'
        'is_valid'
    ),
    [
        (13, 5, 14, 0, 5, 5, True),
        (13, 0, 14, 0, 5, 5, False),  # targeting previous but should be targeting current
        (13, 20, 14, 0, 5, 5, False),  # targeting future slot but should be targeting current
        (29, 10, 30, 10, 20, 10, True),
        (29, 20, 30, 10, 20, 10, False),  # targeting current but should be targeting previous
        (29, 36, 30, 10, 20, 10, False),  # targeting future slot but should be targeting previous
        (10, 10, 10, 10, 10, 10, True),
    ]
)
def test_validate_attestation_justified_slot(sample_attestation_data_params,
                                             attestation_slot,
                                             attestation_justified_slot,
                                             current_slot,
                                             previous_justified_slot,
                                             justified_slot,
                                             epoch_length,
                                             is_valid):
    sample_attestation_data_params['slot'] = attestation_slot
    sample_attestation_data_params['justified_slot'] = attestation_justified_slot
    attestation_data = AttestationData(**sample_attestation_data_params)

    if is_valid:
        validate_attestation_justified_slot(
            attestation_data,
            current_slot,
            previous_justified_slot,
            justified_slot,
            epoch_length,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_justified_slot(
                attestation_data,
                current_slot,
                previous_justified_slot,
                justified_slot,
                epoch_length,
            )


@pytest.mark.parametrize(
    (
        'attestation_justified_block_root,'
        'justified_block_root,'
        'is_valid'
    ),
    [
        (b'\x42' * 32, b'\x35' * 32, False),
        (b'\x42' * 32, b'\x42' * 32, True),
    ]
)
def test_validate_attestation_justified_block_root(sample_attestation_data_params,
                                                   attestation_justified_block_root,
                                                   justified_block_root,
                                                   is_valid):
    sample_attestation_data_params['justified_block_hash'] = attestation_justified_block_root
    attestation_data = AttestationData(**sample_attestation_data_params)

    if is_valid:
        validate_attestation_justified_block_root(
            attestation_data,
            justified_block_root
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_justified_block_root(
                attestation_data,
                justified_block_root
            )
