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
from eth2.beacon.helpers import (
    get_epoch_start_slot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation_aggregate_signature,
    validate_attestation_previous_crosslink_or_root,
    validate_attestation_source_epoch_and_root,
    validate_attestation_crosslink_data_root,
    validate_attestation_slot,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_signed_attestation,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslinks import Crosslink


@pytest.mark.parametrize(
    ('genesis_slot', 'genesis_epoch', 'slots_per_epoch', 'min_attestation_inclusion_delay'),
    [
        (8, 2, 4, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'attestation_slot,'
        'state_slot,'
        'is_valid,'
    ),
    [
        # in bounds at lower end
        (8, 2 + 8, True),
        # in bounds at high end
        (8, 8 + 4, True),
        # attestation_slot < genesis_slot
        (7, 2 + 8, False),
        # state_slot > attestation_data.slot + slots_per_epoch
        (8, 8 + 4 + 1, False),
        # attestation_data.slot + min_attestation_inclusion_delay > state_slot
        (8, 8 - 2, False),
    ]
)
def test_validate_attestation_slot(sample_attestation_data_params,
                                   attestation_slot,
                                   state_slot,
                                   slots_per_epoch,
                                   genesis_slot,
                                   genesis_epoch,
                                   min_attestation_inclusion_delay,
                                   is_valid):
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
    )

    if is_valid:
        validate_attestation_slot(
            attestation_data,
            state_slot,
            slots_per_epoch,
            min_attestation_inclusion_delay,
            genesis_slot,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_slot(
                attestation_data,
                state_slot,
                slots_per_epoch,
                min_attestation_inclusion_delay,
                genesis_slot,
            )


@pytest.mark.parametrize(
    (
        'current_epoch',
        'previous_justified_epoch',
        'current_justified_epoch',
        'previous_justified_root',
        'current_justified_root',
        'slots_per_epoch',
    ),
    [
        (3, 1, 2, b'\x11' * 32, b'\x22' * 32, 8)
    ]
)
@pytest.mark.parametrize(
    (
        'attestation_slot',
        'attestation_source_epoch',
        'attestation_source_root',
        'is_valid',
    ),
    [
        # slot_to_epoch(attestation_data.slot, slots_per_epoch) >= current_epoch
        # attestation_data.source_epoch == state.current_justified_epoch
        (24, 2, b'\x22' * 32, True),
        # attestation_data.source_epoch != state.current_justified_epoch
        (24, 3, b'\x22' * 32, False),
        # attestation_data.source_root != state.current_justified_root
        (24, 2, b'\x33' * 32, False),
        # slot_to_epoch(attestation_data.slot, slots_per_epoch) < current_epoch
        # attestation_data.source_epoch == state.previous_justified_epoch
        (23, 1, b'\x11' * 32, True),
        # attestation_data.source_epoch != state.previous_justified_epoch
        (23, 2, b'\x11' * 32, False),
        # attestation_data.source_root != state.current_justified_root
        (23, 1, b'\x33' * 32, False),
    ]
)
def test_validate_attestation_source_epoch_and_root(
        genesis_state,
        sample_attestation_data_params,
        attestation_slot,
        attestation_source_epoch,
        attestation_source_root,
        current_epoch,
        previous_justified_epoch,
        current_justified_epoch,
        previous_justified_root,
        current_justified_root,
        slots_per_epoch,
        is_valid):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
        previous_justified_epoch=previous_justified_epoch,
        current_justified_epoch=current_justified_epoch,
        previous_justified_root=previous_justified_root,
        current_justified_root=current_justified_root,
    )
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=attestation_slot,
        source_epoch=attestation_source_epoch,
        source_root=attestation_source_root,
    )

    if is_valid:
        validate_attestation_source_epoch_and_root(
            state,
            attestation_data,
            current_epoch,
            slots_per_epoch,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_source_epoch_and_root(
                state,
                attestation_data,
                current_epoch,
                slots_per_epoch,
            )


@pytest.mark.parametrize(
    (
        'attestation_previous_crosslink,'
        'attestation_crosslink_data_root,'
        'state_latest_crosslink,'
        'is_valid,'
    ),
    [
        (
            Crosslink(0, b'\x11' * 32),
            b'\x33' * 32,
            Crosslink(0, b'\x22' * 32),
            False,
        ),
        (
            Crosslink(0, b'\x33' * 32),
            b'\x33' * 32,
            Crosslink(0, b'\x11' * 32),
            False,
        ),
        (
            Crosslink(0, b'\x11' * 32),
            b'\x33' * 32,
            Crosslink(0, b'\x33' * 32),
            True,
        ),
        (
            Crosslink(0, b'\x33' * 32),
            b'\x22' * 32,
            Crosslink(0, b'\x33' * 32),
            True,
        ),
        (
            Crosslink(0, b'\x33' * 32),
            b'\x33' * 32,
            Crosslink(0, b'\x33' * 32),
            True,
        ),
    ]
)
def test_validate_attestation_latest_crosslink(sample_attestation_data_params,
                                               attestation_previous_crosslink,
                                               attestation_crosslink_data_root,
                                               state_latest_crosslink,
                                               slots_per_epoch,
                                               is_valid):
    sample_attestation_data_params['previous_crosslink'] = attestation_previous_crosslink
    sample_attestation_data_params['crosslink_data_root'] = attestation_crosslink_data_root
    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        previous_crosslink=attestation_previous_crosslink,
        crosslink_data_root=attestation_crosslink_data_root,
    )

    if is_valid:
        validate_attestation_previous_crosslink_or_root(
            attestation_data,
            state_latest_crosslink,
            slots_per_epoch=slots_per_epoch,
        )
    else:
        with pytest.raises(ValidationError):
            validate_attestation_previous_crosslink_or_root(
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
        'genesis_slot'
    ),
    [
        (10, 2, 2, 2, True, 0),
        (40, 4, 3, 5, True, 0),
        (20, 5, 3, 2, True, 0),
        (20, 5, 3, 2, False, 0),
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
