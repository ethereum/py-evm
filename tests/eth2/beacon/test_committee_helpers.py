import pytest
import itertools

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    isdistinct,
)

from eth2.beacon.committee_helpers import (
    get_attestation_participants,
    get_beacon_proposer_index,
    get_current_epoch_committee_count,
    get_crosslink_committees_at_slot,
    get_epoch_committee_count,
    get_next_epoch_committee_count,
    get_previous_epoch_committee_count,
    get_shuffling,
)
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)


@pytest.mark.parametrize(
    (
        'active_validator_count,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        # SHARD_COUNT // SLOTS_PER_EPOCH
        (1000, 20, 10, 50, 40),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
        # 1
        (20, 10, 3, 10, 10),
        # 1
        (20, 10, 3, 5, 10),
        # 1
        (40, 5, 10, 2, 5),
    ],
)
def test_get_epoch_committee_count(
        active_validator_count,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        expected_committee_count):
    assert expected_committee_count == get_epoch_committee_count(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        (64, 2, 2, 1024, 32),
    ]
)
def test_get_next_epoch_committee_count(n_validators_state,
                                        shard_count,
                                        slots_per_epoch,
                                        target_committee_size,
                                        expected_committee_count):
    state = n_validators_state

    current_epoch_committee_count = get_current_epoch_committee_count(
        state,
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )
    next_epoch_committee_count = get_next_epoch_committee_count(
        state,
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )
    assert current_epoch_committee_count == expected_committee_count
    assert next_epoch_committee_count == expected_committee_count

    # Exit all validators
    for index, validator in enumerate(state.validator_registry):
        state = state.update_validator_registry(
            validator_index=index,
            validator=validator.copy(
                exit_epoch=state.current_epoch(slots_per_epoch) + 1,
            ),
        )

    current_epoch_committee_count = get_current_epoch_committee_count(
        state,
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )
    next_epoch_committee_count = get_next_epoch_committee_count(
        state,
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )
    assert current_epoch_committee_count == expected_committee_count
    assert next_epoch_committee_count == slots_per_epoch


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'epoch'
    ),
    [
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 1),
        (20, 10, 3, 10, 0),  # active_validators_size < slots_per_epoch * target_committee_size
        (20, 10, 3, 10, 0),
        (20, 10, 3, 10, 1),
    ],
)
def test_get_shuffling_is_complete(activated_genesis_validators,
                                   slots_per_epoch,
                                   target_committee_size,
                                   shard_count,
                                   epoch):
    shuffling = get_shuffling(
        seed=b'\x35' * 32,
        validators=activated_genesis_validators,
        epoch=epoch,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == slots_per_epoch
    assert len(shuffling) > 0
    for committee in shuffling:
        assert len(committee) <= target_committee_size
        assert len(committee) > 0
    validator_indices = tuple(
        itertools.chain(
            [
                validator_index
                for committee in shuffling
                for validator_index in committee
            ]
        )
    )
    assert isdistinct(validator_indices)
    activated_genesis_validator_indices = tuple(
        index
        for index in range(len(activated_genesis_validators))
    )
    assert sorted(validator_indices) == sorted(activated_genesis_validator_indices)


@pytest.mark.parametrize(
    (
        'n, target_committee_size, shard_count, len_active_validators,'
        'previous_shuffling_epoch, current_shuffling_epoch,'
        'get_prev_or_cur_epoch_committee_count,'
        'delayed_activation_epoch'
    ),
    [
        (
            100, 10, 20, 20,
            5, 10,
            get_previous_epoch_committee_count,
            5 + 1,
        ),
        (
            100, 10, 20, 100,
            5, 10,
            get_previous_epoch_committee_count,
            5 + 1,
        ),
        (
            100, 10, 20, 20,
            5, 10,
            get_current_epoch_committee_count,
            10 + 1,
        ),
        (
            100, 10, 20, 100,
            5, 10,
            get_current_epoch_committee_count,
            10 + 1,
        ),
    ],
)
def test_get_prev_or_cur_epoch_committee_count(
        monkeypatch,
        n_validators_state,
        slots_per_epoch,
        n,
        target_committee_size,
        shard_count,
        len_active_validators,
        previous_shuffling_epoch,
        current_shuffling_epoch,
        get_prev_or_cur_epoch_committee_count,
        delayed_activation_epoch):
    from eth2.beacon import committee_helpers

    def mock_get_epoch_committee_count(
            active_validator_count,
            shard_count,
            slots_per_epoch,
            target_committee_size):
        return active_validator_count // shard_count

    monkeypatch.setattr(
        committee_helpers,
        'get_epoch_committee_count',
        mock_get_epoch_committee_count
    )

    state = n_validators_state.copy(
        slot=0,
        previous_shuffling_epoch=previous_shuffling_epoch,
        current_shuffling_epoch=current_shuffling_epoch,
    )
    for index in range(len(state.validator_registry)):
        if index < len_active_validators:
            validator = state.validator_registry[index].copy(
                activation_epoch=0,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )
        else:
            validator = state.validator_registry[index].copy(
                activation_epoch=delayed_activation_epoch,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )

    result_committee_count = get_prev_or_cur_epoch_committee_count(
        state=state,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )
    expected_committee_count = len_active_validators // shard_count

    assert result_committee_count == expected_committee_count


@pytest.mark.parametrize(
    (
        'n,'
        'current_slot,'
        'slot,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'registry_change,'

        'should_reseed,'
        'previous_shuffling_epoch,'
        'current_shuffling_epoch,'
        'shuffling_epoch,'
    ),
    [
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) == current_epoch
        (10, 0, 5, 10, 2, 3, False, False, 0, 0, 0),
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) < current_epoch
        (10, 10, 5, 10, 2, 3, False, False, 0, 1, 0),
        # genesis_epoch < previous_epoch == slot_to_epoch(slot) < current_epoch
        (10, 20, 11, 10, 2, 3, False, False, 1, 2, 1),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == current_epoch
        (10, 10, 11, 10, 2, 3, False, False, 0, 1, 1,),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == next_epoch
        (100, 4, 9, 4, 2, 3, False, False, 0, 1, 2),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == next_epoch
        (100, 4, 9, 4, 2, 3, True, False, 0, 1, 2),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == next_epoch, need_reseed
        # epochs_since_last_registry_update > 1 and is_power_of_two(epochs_since_last_registry_update)  # noqa: E501
        (100, 8, 13, 4, 2, 3, False, True, 1, 2, 3),
    ],
)
def test_get_crosslink_committees_at_slot(
        monkeypatch,
        n_validators_state,
        current_slot,
        slot,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        genesis_epoch,
        committee_config,
        registry_change,
        should_reseed,
        previous_shuffling_epoch,
        current_shuffling_epoch,
        shuffling_epoch):
    # Mock generate_seed
    new_seed = b'\x88' * 32

    def mock_generate_seed(state,
                           epoch,
                           slots_per_epoch,
                           min_seed_lookahead,
                           activation_exit_delay,
                           latest_active_index_roots_length,
                           latest_randao_mixes_length):
        return new_seed

    monkeypatch.setattr(
        'eth2.beacon.helpers.generate_seed',
        mock_generate_seed
    )

    state = n_validators_state.copy(
        slot=current_slot,
        previous_shuffling_epoch=previous_shuffling_epoch,
        current_shuffling_epoch=current_shuffling_epoch,
        previous_shuffling_seed=b'\x11' * 32,
        current_shuffling_seed=b'\x22' * 32,
    )

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        committee_config=committee_config,
        registry_change=registry_change,
    )
    assert len(crosslink_committees_at_slot) > 0
    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee
        assert len(committee) > 0
        assert shard < shard_count

    #
    # Check shuffling_start_shard
    #
    offset = slot % slots_per_epoch

    result_slot_start_shard = crosslink_committees_at_slot[0][1]
    current_committees_per_epoch = get_current_epoch_committee_count(
        state=state,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )
    committees_per_slot = current_committees_per_epoch // slots_per_epoch

    if registry_change:
        shuffling_start_shard = (
            state.current_shuffling_start_shard + current_committees_per_epoch
        ) % shard_count
    else:
        shuffling_start_shard = state.current_shuffling_start_shard
        assert result_slot_start_shard == (
            shuffling_start_shard +
            committees_per_slot * offset
        ) % shard_count

    #
    # Check seed
    #
    epoch = slot_to_epoch(slot, slots_per_epoch)
    current_epoch = state.current_epoch(slots_per_epoch)
    previous_epoch = state.previous_epoch(slots_per_epoch, genesis_epoch)
    next_epoch = current_epoch + 1

    if epoch == current_epoch:
        seed = state.current_shuffling_seed
    elif epoch == previous_epoch:
        seed = state.previous_shuffling_seed
    elif epoch == next_epoch:
        if registry_change or should_reseed:
            seed = new_seed
        else:
            seed = state.current_shuffling_seed

    shuffling = get_shuffling(
        seed=seed,
        validators=state.validator_registry,
        epoch=shuffling_epoch,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    assert shuffling[committees_per_slot * offset] == crosslink_committees_at_slot[0][0]


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'committee,'
        'slot,'
        'success,'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            0,
            True,
        ),
        (
            100,
            64,
            (),
            0,
            False,
        ),
    ]
)
def test_get_beacon_proposer_index(
        monkeypatch,
        num_validators,
        slots_per_epoch,
        committee,
        slot,
        success,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count,
        committee_config):

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )
    if success:
        proposer_index = get_beacon_proposer_index(
            sample_state,
            slot,
            committee_config,
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                committee_config,
            )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'committee,'
        'aggregation_bitfield,'
        'expected'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            b'\00',
            (),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x80',
            (10,),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\xc0',
            (10, 11),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x00\x00',
            ValueError(),
        ),
    ]
)
def test_get_attestation_participants(
        monkeypatch,
        num_validators,
        slots_per_epoch,
        committee,
        aggregation_bitfield,
        expected,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count,
        committee_config,
        sample_attestation_data_params):
    shard = 1

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

    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=0,
        shard=shard,
    )
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            get_attestation_participants(
                state=sample_state,
                attestation_data=attestation_data,
                bitfield=aggregation_bitfield,
                committee_config=committee_config,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            attestation_data=attestation_data,
            bitfield=aggregation_bitfield,
            committee_config=committee_config,
        )

        assert result == expected
