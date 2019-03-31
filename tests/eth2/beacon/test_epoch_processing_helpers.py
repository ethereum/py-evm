import pytest

from cytoolz import (
    pipe,
)

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth.constants import ZERO_HASH32

from eth2._utils.bitfield import (
    set_voted,
    get_empty_bitfield,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.configs import CommitteeConfig
from eth2.beacon.epoch_processing_helpers import (
    get_epoch_boundary_attester_indices,
    get_epoch_boundary_attesting_balances,
    get_inclusion_infos,
    get_previous_epoch_matching_head_attestations,
    get_winning_root_and_participants,
)
from eth2.beacon.helpers import (
    get_effective_balance,
    get_epoch_start_slot,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord


def sampling_attestation_participants(random, committee, target_committee_size):
    """
    Random sampling half the committee.
    `attestation_participants_1` and `attestation_participants_2` are expected to have
    overlapping participants.
    """
    attestation_participants_1 = random.sample(committee, target_committee_size // 2)
    attestation_participants_2 = random.sample(committee, target_committee_size // 2)
    not_attestation_participants_1 = [i for i in committee if i not in attestation_participants_1]
    return attestation_participants_1, attestation_participants_2, not_attestation_participants_1


def get_aggregation_bitfield(attestation_participants, target_committee_size):
    bitfield = get_empty_bitfield(target_committee_size)
    bitfield = pipe(
        bitfield,
        *(
            set_voted(index=committee_index)
            for committee_index in attestation_participants
        )
    )
    return bitfield


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'genesis_slot,'
    ),
    [
        (0),
    ]
)
def test_get_current_and_previous_epoch_attestations(random,
                                                     sample_state,
                                                     genesis_epoch,
                                                     slots_per_epoch,
                                                     sample_attestation_data_params,
                                                     sample_attestation_params):
    num_previous_epoch_attestation, num_current_epoch_attestation = random.sample(
        range(slots_per_epoch),
        2,
    )
    previous_epoch_attestion_slots = random.sample(
        range(slots_per_epoch),
        num_previous_epoch_attestation,
    )
    current_epoch_attestion_slots = random.sample(
        range(slots_per_epoch, slots_per_epoch * 2),
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
        slot=(slots_per_epoch * 2 - 1),
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )
    assert set(previous_epoch_attestations) == set(state.previous_epoch_attestations)
    assert set(current_epoch_attestations) == set(state.current_epoch_attestations)


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'slots_per_epoch,slots_per_historical_root,genesis_slot'
    ),
    [
        (10, 100, 0),
    ]
)
def test_get_previous_epoch_matching_head_attestations(
        random,
        sample_state,
        genesis_epoch,
        slots_per_epoch,
        slots_per_historical_root,
        sample_attestation_data_params,
        sample_attestation_params):
    previous_epoch = 9
    current_epoch = previous_epoch + 1
    current_slot = get_epoch_start_slot(current_epoch + 1, slots_per_epoch) - 1
    latest_block_roots = [
        hash_eth2(b'block_root' + i.to_bytes(1, 'little'))
        for i in range(slots_per_historical_root)
    ]

    num_previous_epoch_attestation = random.sample(range(slots_per_epoch), 1)[0]
    previous_epoch_attestion_slots = random.sample(
        range(
            get_epoch_start_slot(previous_epoch, slots_per_epoch),
            get_epoch_start_slot(current_epoch, slots_per_epoch),
        ),
        num_previous_epoch_attestation,
    )
    num_previous_epoch_head_attestation = random.sample(range(num_previous_epoch_attestation), 1)[0]
    previous_epoch_head_attestion_slots = random.sample(
        previous_epoch_attestion_slots,
        num_previous_epoch_head_attestation,
    )
    previous_epoch_not_head_attestion_slots = set(previous_epoch_attestion_slots).difference(
        set(previous_epoch_head_attestion_slots)
    )

    previous_epoch_head_attestations = []
    for slot in previous_epoch_head_attestion_slots:
        previous_epoch_head_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                    beacon_block_root=latest_block_roots[slot % slots_per_historical_root],
                ),
            )
        )
    previous_epoch_not_head_attestations = []
    for slot in previous_epoch_not_head_attestion_slots:
        previous_epoch_not_head_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                ),
            )
        )

    state = sample_state.copy(
        slot=current_slot,
        latest_block_roots=latest_block_roots,
        previous_epoch_attestations=(
            previous_epoch_head_attestations + previous_epoch_not_head_attestations
        ),
    )

    result = get_previous_epoch_matching_head_attestations(
        state,
        slots_per_epoch,
        genesis_epoch,
        slots_per_historical_root,
    )
    assert set(previous_epoch_head_attestations) == set(result)


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
            # vote tie; higher root value is favored
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
def test_get_winning_root_and_participants(
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
                                              committee_config,
                                              registry_change=False):
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
    root_1_participants_bitfield = get_aggregation_bitfield(
        block_root_1_participants,
        target_committee_size,
    )
    root_2_participants_bitfield = get_aggregation_bitfield(
        block_root_2_participants,
        target_committee_size,
    )
    # `attestions` contains attestation to different block root by different set of participants
    attestations = (
        # Attestation to `crosslink_data_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=root_1_participants_bitfield,
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                previous_crosslink=CrosslinkRecord(
                    epoch=config.GENESIS_EPOCH,
                    crosslink_data_root=ZERO_HASH32,
                ),
                crosslink_data_root=competing_block_roots[0],
            ),
        ),
        # Attestation to `crosslink_data_root_2` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=root_2_participants_bitfield,
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                previous_crosslink=CrosslinkRecord(
                    epoch=config.GENESIS_EPOCH,
                    crosslink_data_root=ZERO_HASH32,
                ),
                crosslink_data_root=competing_block_roots[1],
            ),
        ),
    )

    state = n_validators_state.copy(
        previous_epoch_attestations=attestations,
    )
    effective_balances = {
        index: get_effective_balance(
            state.validator_balances,
            index,
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in range(len(state.validator_registry))
    }

    winning_root, attesting_validator_indices = get_winning_root_and_participants(
        state=state,
        shard=shard,
        effective_balances=effective_balances,
        committee_config=committee_config,
    )
    if len(attesting_validator_indices) == 0:
        assert len(block_root_1_participants) == 0 and len(block_root_2_participants) == 0
    else:
        if len(block_root_1_participants) == len(block_root_2_participants):
            if competing_block_roots[0] > competing_block_roots[1]:
                assert winning_root == competing_block_roots[0]
                assert set(attesting_validator_indices) == set(block_root_1_participants)
            else:
                assert winning_root == competing_block_roots[1]
                assert set(attesting_validator_indices) == set(block_root_2_participants)
        elif len(block_root_1_participants) < len(block_root_2_participants):
            assert winning_root == competing_block_roots[1]
            assert set(attesting_validator_indices) == set(block_root_2_participants)
        else:
            assert winning_root == competing_block_roots[0]
            assert set(attesting_validator_indices) == set(block_root_1_participants)


@settings(max_examples=1)
@given(random=st.randoms())
def test_get_epoch_boundary_attester_indices(monkeypatch,
                                             random,
                                             sample_attestation_params,
                                             sample_attestation_data_params,
                                             sample_state,
                                             committee_config):
    target_committee_size = 16
    committee = tuple([i for i in range(target_committee_size)])

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, sample_attestation_data_params['shard'],),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    block_root_1 = hash_eth2(b'block_root_1')
    block_root_2 = hash_eth2(b'block_root_2')

    (
        attestation_participants_1,
        attestation_participants_2,
        not_attestation_participants_1,
    ) = sampling_attestation_participants(random, committee, target_committee_size)

    # Generate bitfield of each participants set
    aggregation_bitfield_1 = get_aggregation_bitfield(
        attestation_participants_1,
        target_committee_size,
    )
    aggregation_bitfield_2 = get_aggregation_bitfield(
        attestation_participants_2,
        target_committee_size,
    )
    not_aggregation_bitfield_1 = get_aggregation_bitfield(
        not_attestation_participants_1,
        target_committee_size,
    )
    # `attestions` contains attestation to different block root by different set of participants
    attestations = [
        # Attestation to `block_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_1,
            data=AttestationData(**sample_attestation_data_params).copy(
                source_epoch=1,
                target_root=block_root_1,
            ),
        ),
        # Attestation to `block_root_1` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_2,
            data=AttestationData(**sample_attestation_data_params).copy(
                source_epoch=1,
                target_root=block_root_1,
            ),
        ),
        # Attestation to `block_root_2` by `not_attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=not_aggregation_bitfield_1,
            data=AttestationData(**sample_attestation_data_params).copy(
                source_epoch=2,
                target_root=block_root_2,
            ),
        ),
    ]

    block_root_1_attesting_validator = get_epoch_boundary_attester_indices(
        state=sample_state,
        attestations=attestations,
        epoch=1,
        root=block_root_1,
        committee_config=committee_config,
    )
    # Check that result is the union of two participants set
    # `attestation_participants_1` and `attestation_participants_2`
    assert set(block_root_1_attesting_validator) == set(
        attestation_participants_1 + attestation_participants_2)
    assert len(block_root_1_attesting_validator) == len(
        set(attestation_participants_1 + attestation_participants_2))

    block_root_2_attesting_validator = get_epoch_boundary_attester_indices(
        state=sample_state,
        attestations=attestations,
        epoch=2,
        root=block_root_2,
        committee_config=committee_config,
    )
    # Check that result is the `not_attestation_participants_1` set
    assert set(block_root_2_attesting_validator) == set(not_attestation_participants_1)
    assert len(block_root_2_attesting_validator) == len(not_attestation_participants_1)


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'genesis_slot,'
    ),
    [
        (
            16,
            0,
        ),
    ]
)
def test_get_epoch_boundary_attesting_balances(
    monkeypatch,
    random,
    config,
    n,
    n_validators_state,
    sample_attestation_data_params,
    sample_attestation_params,
    max_deposit_amount,
):
    slot = 255
    current_epoch = 3
    previous_epoch = 2
    justified_epoch = 2
    previous_justified_epoch = 1
    target_committee_size = n
    committee = tuple(i for i in range(target_committee_size))

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, sample_attestation_data_params['shard'],),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    current_target_root = hash_eth2(b'block_root_1')
    previous_target_root = hash_eth2(b'block_root_2')
    latest_block_roots = list(None for _ in range(config.SLOTS_PER_HISTORICAL_ROOT))
    latest_block_roots[192] = current_target_root
    latest_block_roots[128] = previous_target_root
    (
        attestation_participants_1,
        attestation_participants_2,
        _,
    ) = sampling_attestation_participants(random, committee, target_committee_size)

    # Generate bitfield of each participants set
    aggregation_bitfield_1 = get_aggregation_bitfield(
        attestation_participants_1,
        target_committee_size,
    )
    aggregation_bitfield_2 = get_aggregation_bitfield(
        attestation_participants_2,
        target_committee_size,
    )

    current_epoch_attestations = (
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_1,
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=194,
                source_epoch=justified_epoch,
                target_root=current_target_root,
            ),
        ),
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_2,
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=193,
                source_epoch=justified_epoch,
                target_root=current_target_root,
            ),
        ),

    )

    previous_epoch_attestations = (
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_1,
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=129,
                source_epoch=previous_justified_epoch,
                target_root=previous_target_root,
            ),
        ),
        Attestation(**sample_attestation_params).copy(
            aggregation_bitfield=aggregation_bitfield_2,
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=130,
                source_epoch=previous_justified_epoch,
                target_root=previous_target_root,
            ),
        ),
    )

    state = n_validators_state.copy(
        slot=slot,
        justified_epoch=justified_epoch,
        previous_justified_epoch=previous_justified_epoch,
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
        latest_block_roots=tuple(latest_block_roots),
    )
    (
        previous_epoch_boundary_attesting_balance,
        current_epoch_boundary_attesting_balance,
    ) = get_epoch_boundary_attesting_balances(
        current_epoch=current_epoch,
        previous_epoch=previous_epoch,
        state=state,
        config=config,
    )
    num_unique_attesters = len(set(attestation_participants_1 + attestation_participants_2))
    assert previous_epoch_boundary_attesting_balance == num_unique_attesters * max_deposit_amount
    assert current_epoch_boundary_attesting_balance == num_unique_attesters * max_deposit_amount


@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'attestation_1_inclusion_slot,attestation_1_data_slot,'
        'attestation_2_inclusion_slot,attestation_2_data_slot,'
        'expected_inclusion_slot,expected_inclusion_distance,'
    ),
    [
        (
            50,
            10,
            5,
            18, 12,
            15, 11,
            15, 4,  # 15 is the smaller inclusion_slot, inclusion_distance is 15-11 = 4
        ),
    ]
)
def test_get_inclusion_infos(
        monkeypatch,
        n,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        attestation_1_inclusion_slot,
        attestation_1_data_slot,
        attestation_2_inclusion_slot,
        attestation_2_data_slot,
        expected_inclusion_slot,
        expected_inclusion_distance,
        sample_attestation_data_params,
        sample_pending_attestation_record_params):
    participating_validator_index = 1
    committee = (1, 2, 3)
    shard = 1
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    aggregation_bitfield = get_empty_bitfield(target_committee_size)
    aggregation_bitfield = set_voted(
        aggregation_bitfield,
        committee.index(participating_validator_index)
    )
    previous_epoch_attestations = [
        PendingAttestationRecord(**sample_pending_attestation_record_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=attestation_1_data_slot,
                shard=shard,
            ),
            aggregation_bitfield=aggregation_bitfield,
            slot_included=attestation_1_inclusion_slot,
        ),
        PendingAttestationRecord(**sample_pending_attestation_record_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                slot=attestation_2_data_slot,
                shard=shard,
            ),
            aggregation_bitfield=aggregation_bitfield,
            slot_included=attestation_2_inclusion_slot,
        ),
    ]

    result = get_inclusion_infos(
        state=n_validators_state,
        attestations=previous_epoch_attestations,
        committee_config=CommitteeConfig(config),
    )
    assert result[participating_validator_index].inclusion_slot == expected_inclusion_slot
    assert result[participating_validator_index].inclusion_distance == expected_inclusion_distance
