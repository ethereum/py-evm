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
    get_shuffling,
    get_previous_epoch_committee_count,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)


@pytest.mark.parametrize(
    (
        'active_validator_count,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        (1000, 20, 10, 50, 40),  # SHARD_COUNT // EPOCH_LENGTH
        (500, 20, 10, 100, 40),  # active_validator_count // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE
        (20, 10, 3, 10, 10),  # 1
        (20, 10, 3, 5, 10),  # 1
        (40, 5, 10, 2, 5),  # 1
    ],
)
def test_get_epoch_committee_count(
        active_validator_count,
        epoch_length,
        target_committee_size,
        shard_count,
        expected_committee_count):
    assert expected_committee_count == get_epoch_committee_count(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'epoch'
    ),
    [
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 1),
        (20, 10, 3, 10, 0),  # active_validators_size < epoch_length * target_committee_size
        (20, 10, 3, 10, 0),
        (20, 10, 3, 10, 1),
    ],
)
def test_get_shuffling_is_complete(activated_genesis_validators,
                                   epoch_length,
                                   target_committee_size,
                                   shard_count,
                                   epoch):
    shuffling = get_shuffling(
        seed=b'\x35' * 32,
        validators=activated_genesis_validators,
        epoch=epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == epoch_length
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
        'previous_calculation_epoch, current_calculation_epoch,'
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
        epoch_length,
        n,
        target_committee_size,
        shard_count,
        len_active_validators,
        previous_calculation_epoch,
        current_calculation_epoch,
        get_prev_or_cur_epoch_committee_count,
        delayed_activation_epoch):
    from eth2.beacon import committee_helpers

    def mock_get_epoch_committee_count(
            active_validator_count,
            shard_count,
            epoch_length,
            target_committee_size):
        return active_validator_count // shard_count

    monkeypatch.setattr(
        committee_helpers,
        'get_epoch_committee_count',
        mock_get_epoch_committee_count
    )

    state = n_validators_state.copy(
        slot=0,
        previous_calculation_epoch=previous_calculation_epoch,
        current_calculation_epoch=current_calculation_epoch,
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
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )
    expected_committee_count = len_active_validators // shard_count

    assert result_committee_count == expected_committee_count


@pytest.mark.parametrize(
    (
        'current_slot,'
        'slot,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) == current_epoch
        (0, 5, 10, 10, 10),
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) < current_epoch
        (10, 5, 10, 10, 10),
        # genesis_epoch < previous_epoch == slot_to_epoch(slot) < current_epoch
        (20, 11, 10, 10, 10),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == current_epoch
        (10, 11, 10, 10, 10),
    ],
)
def test_get_crosslink_committees_at_slot(
        n_validators_state,
        current_slot,
        slot,
        epoch_length,
        target_committee_size,
        shard_count,
        genesis_epoch):

    state = n_validators_state.copy(
        slot=current_slot,
    )

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    assert len(crosslink_committees_at_slot) > 0
    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee
        assert len(committee) > 0
        assert shard < shard_count


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
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
        epoch_length,
        committee,
        slot,
        success,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count):

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
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
            genesis_epoch,
            epoch_length,
            target_committee_size,
            shard_count,
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                genesis_epoch,
                epoch_length,
                target_committee_size,
                shard_count,
            )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
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
        epoch_length,
        committee,
        aggregation_bitfield,
        expected,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count,
        sample_attestation_data_params):
    shard = 1

    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
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
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length,
                target_committee_size=target_committee_size,
                shard_count=shard_count,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            attestation_data=attestation_data,
            bitfield=aggregation_bitfield,
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
            shard_count=shard_count,
        )

        assert result == expected
