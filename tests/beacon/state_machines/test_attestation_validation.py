import pytest

from eth_utils import (
    ValidationError,
)
from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.state_machines.validation import (
    validate_attestation_latest_crosslink_root,
    validate_attestation_justified_block_root,
    validate_attestation_justified_slot,
    validate_attestation_shard_block_root,
    validate_attestation_slot,
)
from eth.beacon.types.attestation_data import (
    AttestationData,
)


@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'current_slot,'
        'epoch_length,'
        'min_attestation_inclusion_delay,'
        'is_valid,'
    ),
    [
        (0, 5, 5, 1, True),
        (0, 5, 5, 5, True),
        (0, 5, 5, 6, False),  # attestation_slot + in_attestation_inclusion_delay > current_slot
        (7, 5, 10, 1, False),  # attestation_slot > current_slot
        (10, 20, 10, 2, True),
        (9, 20, 10, 2, False),  # attestation_slot + EPOCH_LENGTH < current_slot
    ]
)
def test_validate_attestation_slot(sample_attestation_data_params,
                                   attestation_slot,
                                   current_slot,
                                   epoch_length,
                                   min_attestation_inclusion_delay,
                                   is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
    )

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
        'is_valid,'
    ),
    [
        (13, 5, 14, 0, 5, 5, True),
        (13, 0, 14, 0, 5, 5, False),  # targeting previous_justified_slot, should be targeting justified_slot # noqa: E501
        (13, 20, 14, 0, 5, 5, False),  # targeting future slot, should be targeting justified_slot
        (29, 10, 30, 10, 20, 10, True),
        (29, 20, 30, 10, 20, 10, False),  # targeting justified_slot, should be targeting previous_justified_slot # noqa: E501
        (29, 36, 30, 10, 20, 10, False),  # targeting future slot,  should be targeting previous_justified_slot # noqa: E501
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
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
        justified_slot=attestation_justified_slot,
    )

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
        'is_valid,'
    ),
    [
        (b'\x42' * 32, b'\x35' * 32, False),  # attestation.justified_block_root != justified_block_root # noqa: E501
        (b'\x42' * 32, b'\x42' * 32, True),
    ]
)
def test_validate_attestation_justified_block_root(sample_attestation_data_params,
                                                   attestation_justified_block_root,
                                                   justified_block_root,
                                                   is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        justified_block_root=attestation_justified_block_root,
    )

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


@pytest.mark.parametrize(
    (
        'attestation_latest_crosslink_root,'
        'attestation_shard_block_root,'
        'latest_crosslink_shard_block_root,'
        'is_valid,'
    ),
    [
        (b'\x66' * 32, b'\x42' * 32, b'\x35' * 32, False),
        (b'\x42' * 32, b'\x42' * 32, b'\x66' * 32, False),
        (b'\x66' * 32, b'\x42' * 32, b'\x42' * 32, True),
        (b'\x42' * 32, b'\x35' * 32, b'\x42' * 32, True),
        (b'\x42' * 32, b'\x42' * 32, b'\x42' * 32, True),
    ]
)
def test_validate_attestation_latest_crosslink_root(sample_attestation_data_params,
                                                    attestation_latest_crosslink_root,
                                                    attestation_shard_block_root,
                                                    latest_crosslink_shard_block_root,
                                                    is_valid):
    sample_attestation_data_params['latest_crosslink_root'] = attestation_latest_crosslink_root
    sample_attestation_data_params['shard_block_root'] = attestation_shard_block_root
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        latest_crosslink_root=attestation_latest_crosslink_root,
        shard_block_root=attestation_shard_block_root,
    )

    if is_valid:
        validate_attestation_latest_crosslink_root(
            attestation_data,
            latest_crosslink_shard_block_root,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_latest_crosslink_root(
                attestation_data,
                latest_crosslink_shard_block_root,
            )


@pytest.mark.parametrize(
    (
        'attestation_shard_block_root,'
        'is_valid,'
    ),
    [
        (ZERO_HASH32, True),
        (b'\x35' * 32, False),
        (b'\x66' * 32, False),
    ]
)
def test_validate_attestation_shard_block_root(sample_attestation_data_params,
                                               attestation_shard_block_root,
                                               is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        shard_block_root=attestation_shard_block_root,
    )

    if is_valid:
        validate_attestation_shard_block_root(
            attestation_data,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_shard_block_root(
                attestation_data,
            )


def test_validate_attestation_aggregate_signature():
    pass
