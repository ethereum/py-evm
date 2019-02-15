import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth._utils.numeric import (
    int_to_bytes32,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2._utils.bitfield import (
    set_voted,
    get_empty_bitfield,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_epoch_start_slot,
    get_randao_mix,
    slot_to_epoch,
)
from eth2.beacon.epoch_processing_helpers import (
    get_base_reward,
    get_effective_balance,
    get_inclusion_info_map,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _check_if_update_validator_registry,
    _update_latest_active_index_roots,
    process_crosslinks,
    process_final_updates,
    process_rewards_and_penalties,
    process_validator_registry,
    _current_previous_epochs_justifiable,
    _get_finalized_epoch,
    process_justification,
)

from eth2.beacon.types.states import BeaconState
from eth2.beacon.constants import GWEI_PER_ETH


@pytest.mark.parametrize(
    "total_balance,"
    "current_epoch_boundary_attesting_balance,"
    "previous_epoch_boundary_attesting_balance,"
    "expected,",
    (
        (
            1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, (True, True),
        ),
        (
            1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, (True, False),
        ),
        (
            1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, (False, True),
        ),
        (
            1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, (False, False),
        ),
    )
)
def test_current_previous_epochs_justifiable(
        monkeypatch,
        sample_state,
        config,
        expected,
        total_balance,
        previous_epoch_boundary_attesting_balance,
        current_epoch_boundary_attesting_balance):
    current_epoch = 5
    previous_epoch = 4

    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_get_total_balance(validators, epoch, max_deposit_amount):
        return total_balance

    def mock_get_epoch_boundary_attesting_balances(current_epoch, previous_epoch, state, config):
        return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance

    with monkeypatch.context() as m:
        m.setattr(
            epoch_processing,
            'get_total_balance',
            mock_get_total_balance,
        )
        m.setattr(
            epoch_processing,
            'get_epoch_boundary_attesting_balances',
            mock_get_epoch_boundary_attesting_balances,
        )

        assert _current_previous_epochs_justifiable(sample_state,
                                                    current_epoch,
                                                    previous_epoch,
                                                    config) == expected


@pytest.mark.parametrize(
    "justification_bitfield,"
    "previous_justified_epoch,"
    "justified_epoch,"
    "expected,",
    (
        # Rule 1
        (0b111110, 3, 3, (3, 1)),
        # Rule 2
        (0b111110, 4, 4, (4, 2)),
        # Rule 3
        (0b110111, 3, 4, (4, 3)),
        # Rule 4
        (0b110011, 2, 5, (5, 4)),
        # No finalize
        (0b110000, 2, 2, (1, 0)),
    )
)
def test_get_finalized_epoch(justification_bitfield,
                             previous_justified_epoch,
                             justified_epoch,
                             expected):
    previous_epoch = 5
    finalized_epoch = 1
    assert _get_finalized_epoch(justification_bitfield,
                                previous_justified_epoch,
                                justified_epoch,
                                finalized_epoch,
                                previous_epoch,) == expected


def test_justification_without_mock(sample_beacon_state_params,
                                    latest_block_roots_length,
                                    config):

    state = BeaconState(**sample_beacon_state_params).copy(
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
        justification_bitfield=0b0,
    )
    state = process_justification(state, config)
    assert state.justification_bitfield == 0b11


@pytest.mark.parametrize(
    # Each state contains epoch, current_epoch_justifiable, previous_epoch_justifiable,
    # previous_justified_epoch, justified_epoch, justification_bitfield, and finalized_epoch.
    # Specify the last epoch processed state at the end of the items.
    "states,",
    (
        (
            # Trigger R4 to finalize epoch 1
            (0, True, False, 0, 0, 0b0, 0),
            (1, True, True, 0, 0, 0b1, 0),  # R4 finalize 0
            (2, True, True, 0, 1, 0b11, 0),  # R4 finalize 1
            (1, 2, 0b111, 1),
        ),
        (
            # Trigger R2 to finalize epoch 1
            # Trigger R3 to finalize epoch 2
            (2, False, True, 0, 1, 0b11, 0),  # R2 finalize 0
            (3, False, True, 1, 1, 0b110, 0),  # R2 finalize 1
            (4, True, True, 1, 2, 0b1110, 1),  # R3 finalize 2
            (2, 4, 0b11111, 2)
        ),
        (
            # Trigger R1 to finalize epoch 2
            (2, False, True, 0, 1, 0b11, 0),  # R2 finalize 0
            (3, False, True, 1, 1, 0b110, 0),  # R2 finalize 1
            (4, False, True, 1, 2, 0b1110, 1),  # R1 finalize 1
            (5, False, True, 2, 3, 0b11110, 1),  # R1 finalize 2
            (3, 4, 0b111110, 2)
        ),
    ),
)
def test_process_justification(monkeypatch,
                               config,
                               sample_beacon_state_params,
                               states,
                               genesis_epoch=0):
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    for i in range(len(states) - 1):
        (
            current_epoch,
            current_epoch_justifiable,
            previous_epoch_justifiable,
            previous_justified_epoch_before,
            justified_epoch_before,
            justification_bitfield_before,
            finalized_epoch_before,
        ) = states[i]

        (
            previous_justified_epoch_after,
            justified_epoch_after,
            justification_bitfield_after,
            finalized_epoch_after,
        ) = states[i + 1][-4:]
        slot = (current_epoch + 1) * config.SLOTS_PER_EPOCH - 1

        def mock_current_previous_epochs_justifiable(current_epoch, previous_epoch, state, config):
            return current_epoch_justifiable, previous_epoch_justifiable

        with monkeypatch.context() as m:
            m.setattr(
                epoch_processing,
                '_current_previous_epochs_justifiable',
                mock_current_previous_epochs_justifiable,
            )

            state = BeaconState(**sample_beacon_state_params).copy(
                slot=slot,
                previous_justified_epoch=previous_justified_epoch_before,
                justified_epoch=justified_epoch_before,
                justification_bitfield=justification_bitfield_before,
                finalized_epoch=finalized_epoch_before,
            )

            state = process_justification(state, config)

            assert state.previous_justified_epoch == previous_justified_epoch_after
            assert state.justified_epoch == justified_epoch_after
            assert state.justification_bitfield == justification_bitfield_after
            assert state.finalized_epoch == finalized_epoch_after


@pytest.mark.parametrize(
    (
        'num_validators, slots_per_epoch, target_committee_size, shard_count, state_slot,'
        'validator_registry_update_epoch,'
        'finalized_epoch,'
        'has_crosslink,'
        'crosslink_epoch,'
        'expected_need_to_update,'
    ),
    [
        # state.finalized_epoch <= state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 4, False, 0, False
        ),
        # state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 8, True, 4, False,
        ),
        # state.finalized_epoch > state.validator_registry_update_epoch and
        # state.latest_crosslinks[shard].epoch > state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 8, True, 6, True,
        ),
    ]
)
def test_check_if_update_validator_registry(genesis_state,
                                            state_slot,
                                            validator_registry_update_epoch,
                                            finalized_epoch,
                                            has_crosslink,
                                            crosslink_epoch,
                                            expected_need_to_update,
                                            config):
    state = genesis_state.copy(
        slot=state_slot,
        finalized_epoch=finalized_epoch,
        validator_registry_update_epoch=validator_registry_update_epoch,
    )
    if has_crosslink:
        crosslink = CrosslinkRecord(
            epoch=crosslink_epoch,
            shard_block_root=ZERO_HASH32,
        )
        latest_crosslinks = state.latest_crosslinks
        for shard in range(config.SHARD_COUNT):
            latest_crosslinks = update_tuple_item(
                latest_crosslinks,
                shard,
                crosslink,
            )
        state = state.copy(
            latest_crosslinks=latest_crosslinks,
        )

    need_to_update, num_shards_in_committees = _check_if_update_validator_registry(state, config)

    assert need_to_update == expected_need_to_update
    if expected_need_to_update:
        expected_num_shards_in_committees = get_current_epoch_committee_count(
            state,
            shard_count=config.SHARD_COUNT,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            target_committee_size=config.TARGET_COMMITTEE_SIZE,
        )
        assert num_shards_in_committees == expected_num_shards_in_committees
    else:
        assert num_shards_in_committees == 0


@pytest.mark.parametrize(
    (
        'slots_per_epoch,'
        'latest_active_index_roots_length,'
        'state_slot,'
    ),
    [
        (4, 16, 4),
        (4, 16, 64),
    ]
)
def test_update_latest_active_index_roots(genesis_state,
                                          committee_config,
                                          state_slot,
                                          slots_per_epoch,
                                          latest_active_index_roots_length,
                                          activation_exit_delay):
    state = genesis_state.copy(
        slot=state_slot,
    )

    result_state = _update_latest_active_index_roots(state, committee_config)

    # TODO: chanege to hash_tree_root
    index_root = hash_eth2(
        b''.join(
            [
                index.to_bytes(32, 'big')
                for index in get_active_validator_indices(
                    state.validator_registry,
                    # TODO: change to `per-epoch` version
                    slot_to_epoch(state.slot, slots_per_epoch),
                )
            ]
        )
    )

    target_epoch = state.next_epoch(slots_per_epoch) + activation_exit_delay
    assert result_state.latest_active_index_roots[
        target_epoch % latest_active_index_roots_length
    ] == index_root


@pytest.mark.parametrize(
    (
        'num_validators, slots_per_epoch, target_committee_size, shard_count,'
        'latest_randao_mixes_length, min_seed_lookahead, state_slot,'
        'need_to_update,'
        'num_shards_in_committees,'
        'validator_registry_update_epoch,'
        'epochs_since_last_registry_change_is_power_of_two,'
        'current_shuffling_epoch,'
        'latest_randao_mixes,'
        'expected_current_shuffling_epoch,'
    ),
    [
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            2,
            True,  # (state.current_epoch - state.validator_registry_update_epoch) is power of two
            0,
            [int_to_bytes32(i) for i in range(2**10)],
            5,  # expected current_shuffling_epoch is state.next_epoch
        ),
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            1,
            False,  # (state.current_epoch - state.validator_registry_update_epoch) != power of two
            0,
            [int_to_bytes32(i) for i in range(2**10)],
            0,  # expected_current_shuffling_epoch is current_shuffling_epoch because it will not be updated  # noqa: E501
        ),
    ]
)
def test_process_validator_registry(monkeypatch,
                                    genesis_state,
                                    slots_per_epoch,
                                    state_slot,
                                    need_to_update,
                                    num_shards_in_committees,
                                    validator_registry_update_epoch,
                                    epochs_since_last_registry_change_is_power_of_two,
                                    current_shuffling_epoch,
                                    latest_randao_mixes,
                                    expected_current_shuffling_epoch,
                                    activation_exit_delay,
                                    config):
    # Mock check_if_update_validator_registry
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_check_if_update_validator_registry(state, config):
        return need_to_update, num_shards_in_committees

    monkeypatch.setattr(
        epoch_processing,
        '_check_if_update_validator_registry',
        mock_check_if_update_validator_registry
    )

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

    # Set state
    state = genesis_state.copy(
        slot=state_slot,
        validator_registry_update_epoch=validator_registry_update_epoch,
        current_shuffling_epoch=current_shuffling_epoch,
        latest_randao_mixes=latest_randao_mixes,
    )

    result_state = process_validator_registry(state, config)

    assert result_state.previous_shuffling_epoch == state.current_shuffling_epoch
    assert result_state.previous_shuffling_start_shard == state.current_shuffling_start_shard
    assert result_state.previous_shuffling_seed == state.current_shuffling_seed

    if need_to_update:
        assert result_state.current_shuffling_epoch == slot_to_epoch(state_slot, slots_per_epoch)
        assert result_state.current_shuffling_seed == new_seed
        # TODO: Add test for validator registry updates
    else:
        assert (
            result_state.current_shuffling_epoch ==
            expected_current_shuffling_epoch
        )
        # state.current_shuffling_start_shard is left unchanged.
        assert result_state.current_shuffling_start_shard == state.current_shuffling_start_shard

        if epochs_since_last_registry_change_is_power_of_two:
            assert result_state.current_shuffling_seed == new_seed
        else:
            assert result_state.current_shuffling_seed != new_seed


@pytest.mark.parametrize(
    (
        'num_validators,'
        'state_slot,'
        'attestation_slot,'
        'len_latest_attestations,'
        'expected_result_len_latest_attestations,'
        'slots_per_epoch'
    ),
    [
        (10, 4, 4, 2, 2, 4),  # slot_to_epoch(attestation.data.slot) >= state.current_epoch, -> expected_result_len_latest_attestations = len_latest_attestations  # noqa: E501
        (10, 4, 8, 2, 2, 4),  # slot_to_epoch(attestation.data.slot) >= state.current_epoch, -> expected_result_len_latest_attestations = len_latest_attestations  # noqa: E501
        (10, 16, 8, 2, 0, 4),  # slot_to_epoch(attestation.data.slot) < state.current_epoch, -> expected_result_len_latest_attestations = 0  # noqa: E501
    ]
)
def test_process_final_updates(genesis_state,
                               state_slot,
                               attestation_slot,
                               len_latest_attestations,
                               expected_result_len_latest_attestations,
                               config,
                               sample_attestation_params):
    state = genesis_state.copy(
        slot=state_slot,
    )
    current_index = state.next_epoch(config.SLOTS_PER_EPOCH) % config.LATEST_SLASHED_EXIT_LENGTH
    previous_index = state.current_epoch(config.SLOTS_PER_EPOCH) % config.LATEST_SLASHED_EXIT_LENGTH

    # Assume `len_latest_attestations` attestations in state.latest_attestations
    # with attestation.data.slot = attestation_slot
    attestation = Attestation(**sample_attestation_params)
    latest_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=attestation_slot
            )
        )
        for i in range(len_latest_attestations)
    ]

    # Fill latest_slashed_balances
    slashed_balance_of_previous_epoch = 100
    latest_slashed_balances = update_tuple_item(
        state.latest_slashed_balances,
        previous_index,
        slashed_balance_of_previous_epoch,
    )
    state = state.copy(
        latest_slashed_balances=latest_slashed_balances,
        latest_attestations=latest_attestations,
    )

    result_state = process_final_updates(state, config)

    assert (
        (
            result_state.latest_slashed_balances[current_index] ==
            slashed_balance_of_previous_epoch
        ) and (
            result_state.latest_randao_mixes[current_index] == get_randao_mix(
                state=state,
                epoch=state.current_epoch(config.SLOTS_PER_EPOCH),
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            )
        )
    )

    assert len(result_state.latest_attestations) == expected_result_len_latest_attestations
    for attestation in result_state.latest_attestations:
        assert attestation.data.slot >= state_slot - config.SLOTS_PER_EPOCH


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'success_crosslink_in_cur_epoch,'
    ),
    [
        (
            90,
            10,
            9,
            10,
            False,
        ),
        (
            90,
            10,
            9,
            10,
            True,
        ),
    ]
)
def test_process_crosslinks(
        random,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        success_crosslink_in_cur_epoch,
        sample_attestation_data_params,
        sample_attestation_params):
    shard = 1
    shard_block_root = hash_eth2(b'shard_block_root')
    current_slot = config.SLOTS_PER_EPOCH * 2 - 1

    genesis_crosslinks = tuple([
        CrosslinkRecord(epoch=config.GENESIS_EPOCH, shard_block_root=ZERO_HASH32)
        for _ in range(shard_count)
    ])
    state = n_validators_state.copy(
        slot=current_slot,
        latest_crosslinks=genesis_crosslinks,
    )

    # Generate current epoch attestations
    cur_epoch_attestations = []
    for slot_in_cur_epoch in range(state.slot - config.SLOTS_PER_EPOCH, state.slot):
        if len(cur_epoch_attestations) > 0:
            break
        for committee, _shard in get_crosslink_committees_at_slot(
            state,
            slot_in_cur_epoch,
            CommitteeConfig(config),
        ):
            if _shard == shard:
                # Sample validators attesting to this shard.
                # Number of attesting validators sampled depends on `success_crosslink_in_cur_epoch`
                # if True, have >2/3 committee attest
                if success_crosslink_in_cur_epoch:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 + 1))
                else:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 - 1))
                # Generate the bitfield
                aggregation_bitfield = get_empty_bitfield(len(committee))
                for v_index in attesting_validators:
                    aggregation_bitfield = set_voted(
                        aggregation_bitfield, committee.index(v_index))
                # Generate the attestation
                cur_epoch_attestations.append(
                    Attestation(**sample_attestation_params).copy(
                        data=AttestationData(**sample_attestation_data_params).copy(
                            slot=slot_in_cur_epoch,
                            shard=shard,
                            shard_block_root=shard_block_root,
                        ),
                        aggregation_bitfield=aggregation_bitfield,
                    )
                )

    state = state.copy(
        latest_attestations=cur_epoch_attestations,
    )
    assert (state.latest_crosslinks[shard].epoch == config.GENESIS_EPOCH and
            state.latest_crosslinks[shard].shard_block_root == ZERO_HASH32)

    new_state = process_crosslinks(state, config)
    crosslink_record = new_state.latest_crosslinks[shard]
    if success_crosslink_in_cur_epoch:
        attestation = cur_epoch_attestations[0]
        assert (crosslink_record.epoch == slot_to_epoch(current_slot, slots_per_epoch) and
                crosslink_record.shard_block_root == attestation.data.shard_block_root and
                attestation.data.shard_block_root == shard_block_root)
    else:
        assert (crosslink_record.epoch == config.GENESIS_EPOCH and
                crosslink_record.shard_block_root == ZERO_HASH32)


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'finalized_epoch,current_slot,'
        'previous_justified_epoch,'
        'latest_block_roots_length,'
        'num_attesting_validators'
    ),
    [
        (
            50,
            10,
            5,
            10,
            4, 79,  # epochs_since_finality <= 4
            5,
            100,
            3,
        ),
        (
            50,
            10,
            5,
            10,
            3, 79,  # epochs_since_finality > 4
            5,
            100,
            4,
        ),
    ]
)
def test_process_rewards_and_penalties(
        random,
        n_validators_state,
        config,
        genesis_epoch,
        epoch_length,
        target_committee_size,
        shard_count,
        finalized_epoch,
        current_slot,
        previous_justified_epoch,
        latest_block_roots_length,
        num_attesting_validators,
        max_deposit_amount,
        min_attestation_inclusion_delay,
        sample_attestation_data_params,
        sample_pending_attestation_record_params):
    previous_epoch = current_slot // epoch_length - 1
    latest_block_roots = [
        hash_eth2(b'block_root' + i.to_bytes(1, 'big'))
        for i in range(latest_block_roots_length)
    ]
    state = n_validators_state.copy(
        slot=current_slot,
        previous_justified_epoch=previous_justified_epoch,
        finalized_epoch=finalized_epoch,
        latest_block_roots=latest_block_roots,
    )
    # Compute previous epoch committees
    prev_epoch_start_slot = get_epoch_start_slot(previous_epoch, epoch_length)
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + epoch_length)
    ]

    # Record which validators attest during each slot for reward collation.
    each_slot_attestion_validators_list = []

    # First, have attestion on every slot of previous epoch.
    # Then we can randomly pick from the attestations to change their
    # property, e.g. justified_epoch, epoch_boundary_root, etc.
    prev_epoch_attestations = []
    for i in range(epoch_length):
        committee, shard = prev_epoch_crosslink_committees[i]
        # Randomly sample `num_attesting_validators` validators
        # from the committee to attest in this slot.
        shard_block_root_attesting_validators = random.sample(
            committee,
            num_attesting_validators,
        )
        each_slot_attestion_validators_list.append(shard_block_root_attesting_validators)
        participants_bitfield = get_empty_bitfield(target_committee_size)
        for index in shard_block_root_attesting_validators:
            participants_bitfield = set_voted(participants_bitfield, committee.index(index))
        data_slot = i + previous_epoch * epoch_length
        prev_epoch_attestations.append(
            PendingAttestationRecord(**sample_pending_attestation_record_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=data_slot,
                    shard=shard,
                ),
                aggregation_bitfield=participants_bitfield,
                slot_included=(data_slot + min_attestation_inclusion_delay),
            )
        )

    # Randomly pick from previous epoch attestations and turn them
    # into previous epoch 'justified' attestation
    num_previous_epoch_justified_attestation = epoch_length // 2
    previous_epoch_justified_attestion_slots = random.sample(
        range(epoch_length),
        num_previous_epoch_justified_attestation,
    )
    for slot in previous_epoch_justified_attestion_slots:
        prev_epoch_attestations[slot] = prev_epoch_attestations[slot].copy(
            data=prev_epoch_attestations[slot].data.copy(
                justified_epoch=previous_justified_epoch,
            ),
        )

    # Randomly pick from previous epoch attestations and turn them
    # into previous epoch 'boundary' attestation
    num_previous_epoch_boundary_attestation = epoch_length // 2
    previous_epoch_boundary_attestion_slots = random.sample(
        range(epoch_length),
        num_previous_epoch_boundary_attestation,
    )
    epoch_boundary_root = latest_block_roots[prev_epoch_start_slot % latest_block_roots_length]
    for slot in previous_epoch_boundary_attestion_slots:
        prev_epoch_attestations[slot] = prev_epoch_attestations[slot].copy(
            data=prev_epoch_attestations[slot].data.copy(
                epoch_boundary_root=epoch_boundary_root,
            ),
        )

    # Randomly pick from previous epoch attestations and turn them
    # into previous epoch 'head' attestation
    num_previous_epoch_head_attestation = epoch_length // 2
    previous_epoch_head_attestion_slots = random.sample(
        range(epoch_length),
        num_previous_epoch_head_attestation,
    )
    for slot in previous_epoch_head_attestion_slots:
        prev_epoch_attestations[slot] = prev_epoch_attestations[slot].copy(
            data=prev_epoch_attestations[slot].data.copy(
                beacon_block_root=latest_block_roots[
                    prev_epoch_attestations[slot].data.slot % latest_block_roots_length],
            ),
        )

    state = state.copy(
        latest_attestations=prev_epoch_attestations,
    )

    # Process the rewards and penalties
    new_state = process_rewards_and_penalties(state, config)

    # Verify validators' balance
    import functools
    epoch_justified_attesting_validators = set(
        functools.reduce(
            lambda tuple_a, tuple_b: tuple_a + tuple_b,
            [
                each_slot_attestion_validators_list[slot]
                for slot in previous_epoch_justified_attestion_slots
            ]
        )
    )

    epoch_boundary_attesting_validators = set(
        functools.reduce(
            lambda tuple_a, tuple_b: tuple_a + tuple_b,
            [
                each_slot_attestion_validators_list[slot]
                for slot in previous_epoch_boundary_attestion_slots
            ]
        )
    ).intersection(epoch_justified_attesting_validators)

    epoch_head_attesting_validators = set(
        functools.reduce(
            lambda tuple_a, tuple_b: tuple_a + tuple_b,
            [
                each_slot_attestion_validators_list[slot]
                for slot in previous_epoch_head_attestion_slots
            ]
        )
    )

    inclusion_slot_map, inclusion_distance_map = get_inclusion_info_map(
        state=state,
        attestations=prev_epoch_attestations,
        committee_config=CommitteeConfig(config),
    )

    active_validators = set(
        [
            i for i in range(len(state.validator_registry))
        ]
    )
    attesting_validators = set(
        functools.reduce(
            lambda a, b: a + b,
            each_slot_attestion_validators_list,
        )
    )

    validator_balance = max_deposit_amount
    total_active_balance = len(active_validators) * validator_balance

    # Reward each validator gains after `process_rewards_and_penalties`.
    # Initialized to 0 for each validator.
    reward_received_map = {
        index: 0
        for index in range(len(state.validator_balances))
    }

    epochs_since_finality = state.next_epoch(epoch_length) - state.finalized_epoch
    if epochs_since_finality <= 4:
        # Rewards/penalties for justified epoch
        total_justified_attesting_balance = (
            len(epoch_justified_attesting_validators) * validator_balance
        )
        for index in epoch_justified_attesting_validators:
            reward = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            ) * total_justified_attesting_balance // total_active_balance
            reward_received_map[index] += reward
        excluded_active_validators_indices = active_validators.difference(
            epoch_justified_attesting_validators)
        for index in excluded_active_validators_indices:
            penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            reward_received_map[index] -= penalty

        # Rewards/penalties for epoch boundary
        total_boundary_attesting_balance = (
            len(epoch_boundary_attesting_validators) * validator_balance
        )
        for index in epoch_boundary_attesting_validators:
            reward = (
                get_base_reward(
                    state=state,
                    index=index,
                    previous_total_balance=total_active_balance,
                    base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                    max_deposit_amount=max_deposit_amount,
                ) * total_boundary_attesting_balance // total_active_balance
            )
            reward_received_map[index] += reward
        excluded_active_validators_indices = active_validators.difference(
            set(epoch_boundary_attesting_validators))
        for index in excluded_active_validators_indices:
            penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            reward_received_map[index] -= penalty

        # Rewards/penalties for epoch head
        total_head_attesting_balance = len(epoch_head_attesting_validators) * validator_balance
        for index in epoch_head_attesting_validators:
            reward = (
                get_base_reward(
                    state=state,
                    index=index,
                    previous_total_balance=total_active_balance,
                    base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                    max_deposit_amount=max_deposit_amount,
                ) * total_head_attesting_balance // total_active_balance
            )
            reward_received_map[index] += reward
        excluded_active_validators_indices = active_validators.difference(
            set(epoch_head_attesting_validators))
        for index in excluded_active_validators_indices:
            penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            reward_received_map[index] -= penalty

        # Rewards for attestation inclusion for validator
        for index in attesting_validators:
            reward = (
                get_base_reward(
                    state=state,
                    index=index,
                    previous_total_balance=total_active_balance,
                    base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                    max_deposit_amount=max_deposit_amount,
                ) * min_attestation_inclusion_delay // inclusion_distance_map[index]
            )
            reward_received_map[index] += reward
    # epochs_since_finality > 4
    else:
        # Penalties for active validators not in justified attesting validators
        excluded_active_validators_indices = active_validators.difference(
            set(epoch_justified_attesting_validators))
        for index in excluded_active_validators_indices:
            inactivity_penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            ) + (
                get_effective_balance(state.validator_balances, index, max_deposit_amount) *
                epochs_since_finality // config.INACTIVITY_PENALTY_QUOTIENT // 2
            )
            reward_received_map[index] -= inactivity_penalty

        # Penalties for active validators not in boundary attesting validators
        excluded_active_validators_indices = active_validators.difference(
            set(epoch_boundary_attesting_validators))
        for index in excluded_active_validators_indices:
            inactivity_penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            ) + (
                get_effective_balance(state.validator_balances, index, max_deposit_amount) *
                epochs_since_finality // config.INACTIVITY_PENALTY_QUOTIENT // 2
            )
            reward_received_map[index] -= inactivity_penalty

        # Penalties for active validators not in head attesting validators
        excluded_active_validators_indices = active_validators.difference(
            set(epoch_head_attesting_validators))
        for index in excluded_active_validators_indices:
            penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            reward_received_map[index] -= penalty

        # Penalties for penalized active validators
        for index in active_validators:
            penalized_epoch = state.validator_registry[index].penalized_epoch
            if penalized_epoch <= state.current_epoch(epoch_length):
                base_reward = get_base_reward(
                    state=state,
                    index=index,
                    previous_total_balance=total_active_balance,
                    base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                    max_deposit_amount=max_deposit_amount,
                )
                inactivity_penalty = base_reward + (
                    get_effective_balance(
                        state.validator_balances,
                        index,
                        max_deposit_amount
                    ) * epochs_since_finality // config.INACTIVITY_PENALTY_QUOTIENT // 2
                )
                penalty = 2 * inactivity_penalty + base_reward
                reward_received_map[index] -= penalty

        # Penalties for attesting validators
        for index in attesting_validators:
            base_reward = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            penalty = (
                base_reward -
                base_reward * config.MIN_ATTESTATION_INCLUSION_DELAY // inclusion_distance_map[index]  # noqa: E501
            )
            reward_received_map[index] -= penalty

    # Rewards for attestion inclusion for proposer
    for index in attesting_validators:
        proposer_index = get_beacon_proposer_index(
            state,
            inclusion_slot_map[index],
            CommitteeConfig(config),
        )
        reward = get_base_reward(
            state=state,
            index=index,
            previous_total_balance=total_active_balance,
            base_reward_quotient=config.BASE_REWARD_QUOTIENT,
            max_deposit_amount=max_deposit_amount,
        ) // config.INCLUDER_REWARD_QUOTIENT
        reward_received_map[proposer_index] = reward_received_map[proposer_index] + reward

    # Rewards/penalties for attesting/not attesting crosslink committee
    for i in range(epoch_length):
        crosslink_committee, shard = prev_epoch_crosslink_committees[i]
        attesting_validators = each_slot_attestion_validators_list[i]
        total_attesting_balance = len(attesting_validators) * validator_balance
        total_committee_balance = len(crosslink_committee) * validator_balance
        for index in attesting_validators:
            reward = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            ) * total_attesting_balance // total_committee_balance
            reward_received_map[index] += reward
        for index in set(crosslink_committee).difference(attesting_validators):
            penalty = get_base_reward(
                state=state,
                index=index,
                previous_total_balance=total_active_balance,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                max_deposit_amount=max_deposit_amount,
            )
            reward_received_map[index] -= penalty

    # Check the rewards/penalties match
    for index in range(len(state.validator_balances)):
        updated_balance = state.validator_balances[index] + reward_received_map[index]
        assert new_state.validator_balances[index] == updated_balance
