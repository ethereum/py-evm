import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation_aggregate_signature,
    validate_attestation_latest_crosslink_root,
    validate_attestation_justified_block_root,
    validate_attestation_justified_epoch,
    validate_attestation_shard_block_root,
    validate_attestation_slot,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestation,
)
from eth2.beacon.types.attestation_data import AttestationData


@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'current_slot,'
        'epoch_length,'
        'min_attestation_inclusion_delay,'
        'is_valid,'
    ),
    [
        (0, 5, 5, 1, True),  # in bounds at lower end
        (0, 5, 5, 5, True),  # in bounds at high end
        (0, 5, 5, 6, False),  # attestation_slot + min_attestation_inclusion_delay > current_slot
        (7, 5, 10, 1, False),  # attestation_slot > current_slot
        (10, 20, 10, 2, True),  # in bounds at lower end
        (7, 20, 10, 2, False),  # attestation_slot + EPOCH_LENGTH < current_slot - inclusion_delay
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
        'attestation_justified_epoch,'
        'current_epoch,'
        'previous_justified_epoch,'
        'justified_epoch,'
        'epoch_length,'
        'is_valid,'
    ),
    [
        (13, 1, 2, 0, 1, 5, True),
        (13, 0, 2, 0, 1, 5, False),  # targeting previous_justified_epoch, should be targeting justified_epoch # noqa: E501
        (13, 4, 2, 0, 1, 5, False),  # targeting future epoch, should be targeting justified_epoch
        (29, 1, 3, 1, 2, 10, True),
        (29, 2, 3, 1, 2, 10, False),  # targeting justified_epoch, should be targeting previous_justified_epoch # noqa: E501
        (29, 3, 3, 1, 2, 10, False),  # targeting future epoch, should be targeting previous_justified_epoch # noqa: E501
        (10, 1, 1, 1, 1, 10, True),
    ]
)
def test_validate_attestation_justified_epoch(
        sample_attestation_data_params,
        attestation_slot,
        attestation_justified_epoch,
        current_epoch,
        previous_justified_epoch,
        justified_epoch,
        epoch_length,
        is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
        justified_epoch=attestation_justified_epoch,
    )

    if is_valid:
        validate_attestation_justified_epoch(
            attestation_data,
            current_epoch,
            previous_justified_epoch,
            justified_epoch,
            epoch_length,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_justified_epoch(
                attestation_data,
                current_epoch,
                previous_justified_epoch,
                justified_epoch,
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
        'latest_crosslink_root,'
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
                                                    latest_crosslink_root,
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
            latest_crosslink_root,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_latest_crosslink_root(
                attestation_data,
                latest_crosslink_root,
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


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'is_valid,'
    ),
    [
        (10, 2, 2, 2, True),
        (40, 4, 3, 5, True),
        (20, 5, 3, 2, True),
        (20, 5, 3, 2, False),
    ],
)
def test_validate_attestation_aggregate_signature(genesis_state,
                                                  epoch_length,
                                                  random,
                                                  sample_attestation_data_params,
                                                  is_valid,
                                                  genesis_epoch,
                                                  target_committee_size,
                                                  shard_count,
                                                  keymap):
    state = genesis_state

    # choose committee
    slot = 0
    crosslink_committee = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )[0]
    committee, shard = crosslink_committee
    committee_size = len(committee)
    assert committee_size > 0

    # randomly select 3/4 participants from committee
    votes_count = len(committee) * 3 // 4
    assert votes_count > 0

    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=slot,
        shard=shard,
    )

    attestation = create_mock_signed_attestation(
        state,
        attestation_data,
        committee,
        votes_count,
        keymap,
        epoch_length,
    )

    if is_valid:
        validate_attestation_aggregate_signature(
            state,
            attestation,
            genesis_epoch,
            epoch_length,
            target_committee_size,
            shard_count,
        )
    else:
        # mess up signature
        attestation = attestation.copy(
            aggregate_signature=(
                attestation.aggregate_signature[0] + 10,
                attestation.aggregate_signature[1] - 1
            )
        )
        with pytest.raises(ValidationError):
            validate_attestation_aggregate_signature(
                state,
                attestation,
                genesis_epoch,
                epoch_length,
                target_committee_size,
                shard_count,
            )
