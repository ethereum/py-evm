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
    validate_attestation_crosslink_data_root,
    validate_attestation_slot,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestation,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslink_records import CrosslinkRecord


@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'current_slot,'
        'slots_per_epoch,'
        'min_attestation_inclusion_delay,'
        'is_valid,'
    ),
    [
        # in bounds at lower end
        (0, 5, 5, 1, True),
        # in bounds at high end
        (0, 5, 5, 5, True),
        # attestation_slot + min_attestation_inclusion_delay > current_slot
        (0, 5, 5, 6, False),
        # attestation_slot > current_slot
        (7, 5, 10, 1, False),
        # in bounds at lower end
        (10, 20, 10, 2, True),
        # attestation_slot + SLOTS_PER_EPOCH < current_slot - inclusion_delay
        (7, 20, 10, 2, False),
    ]
)
def test_validate_attestation_slot(sample_attestation_data_params,
                                   attestation_slot,
                                   current_slot,
                                   slots_per_epoch,
                                   min_attestation_inclusion_delay,
                                   is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
    )

    if is_valid:
        validate_attestation_slot(
            attestation_data,
            current_slot,
            slots_per_epoch,
            min_attestation_inclusion_delay,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_slot(
                attestation_data,
                current_slot,
                slots_per_epoch,
                min_attestation_inclusion_delay,
            )


@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'attestation_justified_epoch,'
        'current_epoch,'
        'previous_justified_epoch,'
        'justified_epoch,'
        'slots_per_epoch,'
        'is_valid,'
    ),
    [
        # slot_to_epoch(attestation_data.slot + 1, slots_per_epoch) >= current_epoch
        (23, 2, 3, 1, 2, 8, True),  # attestation_data.justified_epoch == justified_epoch
        (23, 1, 3, 1, 2, 8, False),  # attestation_data.justified_epoch != justified_epoch
        # slot_to_epoch(attestation_data.slot + 1, slots_per_epoch) < current_epoch
        (22, 1, 3, 1, 2, 8, True),  # attestation_data.justified_epoch == previous_justified_epoch
        (22, 2, 3, 1, 2, 8, False),  # attestation_data.justified_epoch != previous_justified_epoch
    ]
)
def test_validate_attestation_justified_epoch(
        sample_attestation_data_params,
        attestation_slot,
        attestation_justified_epoch,
        current_epoch,
        previous_justified_epoch,
        justified_epoch,
        slots_per_epoch,
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
            slots_per_epoch,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_justified_epoch(
                attestation_data,
                current_epoch,
                previous_justified_epoch,
                justified_epoch,
                slots_per_epoch,
            )


@pytest.mark.parametrize(
    (
        'attestation_justified_block_root,'
        'justified_block_root,'
        'is_valid,'
    ),
    [
        (b'\x33' * 32, b'\x22' * 32, False),  # attestation.justified_block_root != justified_block_root # noqa: E501
        (b'\x33' * 32, b'\x33' * 32, True),
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
        'attestation_latest_crosslink,'
        'attestation_crosslink_data_root,'
        'state_latest_crosslink,'
        'is_valid,'
    ),
    [
        (
            CrosslinkRecord(0, b'\x11' * 32),
            b'\x33' * 32,
            CrosslinkRecord(0, b'\x22' * 32),
            False,
        ),
        (
            CrosslinkRecord(0, b'\x33' * 32),
            b'\x33' * 32,
            CrosslinkRecord(0, b'\x11' * 32),
            False,
        ),
        (
            CrosslinkRecord(0, b'\x11' * 32),
            b'\x33' * 32,
            CrosslinkRecord(0, b'\x33' * 32),
            True,
        ),
        (
            CrosslinkRecord(0, b'\x33' * 32),
            b'\x22' * 32,
            CrosslinkRecord(0, b'\x33' * 32),
            True,
        ),
        (
            CrosslinkRecord(0, b'\x33' * 32),
            b'\x33' * 32,
            CrosslinkRecord(0, b'\x33' * 32),
            True,
        ),
    ]
)
def test_validate_attestation_latest_crosslink(sample_attestation_data_params,
                                               attestation_latest_crosslink,
                                               attestation_crosslink_data_root,
                                               state_latest_crosslink,
                                               slots_per_epoch,
                                               is_valid):
    sample_attestation_data_params['latest_crosslink'] = attestation_latest_crosslink
    sample_attestation_data_params['crosslink_data_root'] = attestation_crosslink_data_root
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        latest_crosslink=attestation_latest_crosslink,
        crosslink_data_root=attestation_crosslink_data_root,
    )

    if is_valid:
        validate_attestation_latest_crosslink_root(
            attestation_data,
            state_latest_crosslink,
            slots_per_epoch=slots_per_epoch,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_latest_crosslink_root(
                attestation_data,
                state_latest_crosslink,
                slots_per_epoch=slots_per_epoch,
            )


@pytest.mark.parametrize(
    (
        'attestation_crosslink_data_root,'
        'is_valid,'
    ),
    [
        (ZERO_HASH32, True),
        (b'\x22' * 32, False),
        (b'\x11' * 32, False),
    ]
)
def test_validate_attestation_crosslink_data_root(sample_attestation_data_params,
                                                  attestation_crosslink_data_root,
                                                  is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        crosslink_data_root=attestation_crosslink_data_root,
    )

    if is_valid:
        validate_attestation_crosslink_data_root(
            attestation_data,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_crosslink_data_root(
                attestation_data,
            )


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
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
                                                  slots_per_epoch,
                                                  random,
                                                  sample_attestation_data_params,
                                                  is_valid,
                                                  target_committee_size,
                                                  shard_count,
                                                  keymap,
                                                  committee_config):
    state = genesis_state

    # choose committee
    slot = 0
    crosslink_committee = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        committee_config=committee_config,
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
        slots_per_epoch,
    )

    if is_valid:
        validate_attestation_aggregate_signature(
            state,
            attestation,
            committee_config,
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
                committee_config,
            )
