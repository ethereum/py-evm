import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth_utils import (
    big_endian_to_int,
)

from eth2._utils.bitfield import (
    set_voted,
    get_empty_bitfield,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.epoch_processing_helpers import (
    get_attesting_validator_indices,
    get_current_epoch_attestations,
    get_previous_epoch_attestations,
    get_winning_root,
)
from eth2.beacon.exceptions import NoWinningRootError
from eth2.beacon.helpers import (
    get_effective_balance,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'target_committee_size,'
        'shard_count'
    ),
    [
        (
            16,
            32,
        ),
    ]
)
def test_get_attesting_validator_indices(
        random,
        monkeypatch,
        target_committee_size,
        shard_count,
        genesis_epoch,
        committee_config,
        sample_state,
        sample_attestation_data_params,
        sample_attestation_params):
    shard = 1
    committee = tuple([i for i in range(target_committee_size)])

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    # Validators attesting to two shard block roots
    shard_block_root_1 = hash_eth2(b'shard_block_root_1')
    shard_block_root_2 = hash_eth2(b'shard_block_root_2')

    # Random sampling half the committee.
    # `attestation_participants_1` and `attestation_participants_2` are expected to have
    # overlapping participants.
    attestation_participants_1 = random.sample(committee, target_committee_size // 2)
    attestation_participants_2 = random.sample(committee, target_committee_size // 2)
    not_attestation_participants_1 = [i for i in committee if i not in attestation_participants_1]

    # Generate bitfield of each participants set
    aggregation_bitfield_1 = get_empty_bitfield(target_committee_size)
    aggregation_bitfield_2 = get_empty_bitfield(target_committee_size)
    not_aggregation_bitfield_1 = get_empty_bitfield(target_committee_size)
    for committee_index_1, committee_index_2, committee_index_3 in zip(
            attestation_participants_1, attestation_participants_2, not_attestation_participants_1):
        aggregation_bitfield_1 = set_voted(aggregation_bitfield_1, committee_index_1)
        aggregation_bitfield_2 = set_voted(aggregation_bitfield_2, committee_index_2)
        not_aggregation_bitfield_1 = set_voted(not_aggregation_bitfield_1, committee_index_3)

    # `attestions` contains attestation to different block root by different set of participants
    attestations = [
        # Attestation to `shard_block_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_1,
            ),
            aggregation_bitfield=aggregation_bitfield_1
        ),
        # Attestation to `shard_block_root_1` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_1,
            ),
            aggregation_bitfield=aggregation_bitfield_2
        ),
        # Attestation to `shard_block_root_2` by `not_attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_2,
            ),
            aggregation_bitfield=not_aggregation_bitfield_1
        ),
    ]

    shard_block_root_1_attesting_validator = get_attesting_validator_indices(
        state=sample_state,
        attestations=attestations,
        shard=shard,
        shard_block_root=shard_block_root_1,
        committee_config=committee_config,
    )
    # Check that result is the union of two participants set
    # `attestation_participants_1` and `attestation_participants_2`
    assert set(shard_block_root_1_attesting_validator) == set(
        attestation_participants_1 + attestation_participants_2)
    assert len(shard_block_root_1_attesting_validator) == len(
        set(attestation_participants_1 + attestation_participants_2))

    shard_block_root_2_attesting_validator = get_attesting_validator_indices(
        state=sample_state,
        attestations=attestations,
        shard=shard,
        shard_block_root=shard_block_root_2,
        committee_config=committee_config,
    )
    # Check that result is the `not_attestation_participants_1` set
    assert set(shard_block_root_2_attesting_validator) == set(not_attestation_participants_1)
    assert len(shard_block_root_2_attesting_validator) == len(not_attestation_participants_1)


@settings(max_examples=1)
@given(random=st.randoms())
def test_get_current_and_previous_epoch_attestations(random,
                                                     sample_state,
                                                     genesis_epoch,
                                                     epoch_length,
                                                     sample_attestation_data_params,
                                                     sample_attestation_params):
    num_previous_epoch_attestation, num_current_epoch_attestation = random.sample(
        range(epoch_length),
        2,
    )
    previous_epoch_attestion_slots = random.sample(
        range(epoch_length),
        num_previous_epoch_attestation,
    )
    current_epoch_attestion_slots = random.sample(
        range(epoch_length, epoch_length * 2),
        num_current_epoch_attestation,
    )

    previous_epoch_attestations = []
    for slot in previous_epoch_attestion_slots:
        previous_epoch_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                ),
            )
        )
    current_epoch_attestations = []
    for slot in current_epoch_attestion_slots:
        current_epoch_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                ),
            )
        )

    state = sample_state.copy(
        slot=(epoch_length * 2 - 1),
        latest_attestations=(previous_epoch_attestations + current_epoch_attestations),
    )
    assert set(previous_epoch_attestations) == set(
        get_previous_epoch_attestations(state, epoch_length, genesis_epoch))
    assert set(current_epoch_attestations) == set(
        get_current_epoch_attestations(state, epoch_length))


@settings(max_examples=10)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'target_committee_size,'
        'block_root_1_participants,'
        'block_root_2_participants,'
    ),
    [
        (
            16,
            (1, 3),
            (2, 4, 6, 8)
        ),
        (
            16,
            # vote tie; lower root value is favored
            (1, 3, 5, 7),
            (2, 4, 6, 8)
        ),
        (
            16,
            # no votes; no winning root
            (),
            ()
        ),
    ]
)
def test_get_winning_root(
        random,
        monkeypatch,
        target_committee_size,
        block_root_1_participants,
        block_root_2_participants,
        config,
        committee_config,
        n_validators_state,
        sample_attestation_data_params,
        sample_attestation_params):
    shard = 1
    committee = tuple([i for i in range(target_committee_size)])

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    competing_block_roots = [
        hash_eth2(bytearray(random.getrandbits(8) for _ in range(10))),
        hash_eth2(bytearray(random.getrandbits(8) for _ in range(10)))
    ]

    # Generate bitfield of each participants set
    root_1_participants_bitfield = get_empty_bitfield(target_committee_size)
    root_2_participants_bitfield = get_empty_bitfield(target_committee_size)
    for i in block_root_1_participants:
        root_1_participants_bitfield = set_voted(root_1_participants_bitfield, i)
    for i in block_root_2_participants:
        root_2_participants_bitfield = set_voted(root_2_participants_bitfield, i)

    # `attestions` contains attestation to different block root by different set of participants
    attestations = [
        # Attestation to `shard_block_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=competing_block_roots[0],
            ),
            aggregation_bitfield=root_1_participants_bitfield
        ),
        # Attestation to `shard_block_root_2` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=competing_block_roots[1],
            ),
            aggregation_bitfield=root_2_participants_bitfield
        ),
    ]

    try:
        winning_root, attesting_balance = get_winning_root(
            state=n_validators_state,
            shard=shard,
            attestations=attestations,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
            committee_config=committee_config,
        )
        attesting_validators_indices = get_attesting_validator_indices(
            state=n_validators_state,
            attestations=attestations,
            shard=shard,
            shard_block_root=winning_root,
            committee_config=committee_config,
        )
        total_attesting_balance = sum(
            get_effective_balance(
                n_validators_state.validator_balances,
                i,
                config.MAX_DEPOSIT_AMOUNT
            )
            for i in attesting_validators_indices
        )
        assert attesting_balance == total_attesting_balance
    except NoWinningRootError:
        assert len(block_root_1_participants) == 0 and len(block_root_2_participants) == 0
    else:
        if len(block_root_1_participants) == len(block_root_2_participants):
            root_1_as_int = big_endian_to_int(competing_block_roots[0])
            root_2_as_int = big_endian_to_int(competing_block_roots[1])
            if root_1_as_int < root_2_as_int:
                assert winning_root == competing_block_roots[0]
            else:
                assert winning_root == competing_block_roots[1]
        elif len(block_root_1_participants) < len(block_root_2_participants):
            assert winning_root == competing_block_roots[1]
        else:
            assert winning_root == competing_block_roots[0]
