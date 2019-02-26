import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth._utils.numeric import (
    int_to_bytes32,
    integer_squareroot
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
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_epoch_start_slot,
    get_randao_mix,
    slot_to_epoch,
)
from eth2.beacon.epoch_processing_helpers import (
    get_base_reward,
    get_effective_balance,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.datastructures.inclusion_info import InclusionInfo
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _check_if_update_validator_registry,
    _update_latest_active_index_roots,
    process_crosslinks,
    process_final_updates,
    _process_rewards_and_penalties_for_attestation_inclusion,
    _process_rewards_and_penalties_for_crosslinks,
    _process_rewards_and_penalties_for_finality,
    process_validator_registry,
    _current_previous_epochs_justifiable,
    _get_finalized_epoch,
    process_justification,
)

from eth2.beacon.types.states import BeaconState
from eth2.beacon.constants import GWEI_PER_ETH


#
# Justification
#
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


#
# Crosslink
#
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


#
# Rewards and penalties
#
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'min_attestation_inclusion_delay,'
        'inactivity_penalty_quotient,'
    ),
    [
        (
            10,
            2,
            5,
            2,
            4,
            10,
        )
    ]
)
@pytest.mark.parametrize(
    (
        'finalized_epoch,current_slot,'
        'penalized_validator_indices,'
        'previous_epoch_active_validator_indices,'
        'previous_epoch_attester_indices,'
        'previous_epoch_boundary_head_attester_indices,'
        'inclusion_distances,'
        'effective_balance,base_reward,'
        'expected_rewards_received'
    ),
    [
        (
            4, 15,  # epochs_since_finality <= 4
            {6, 7},
            {0, 1, 2, 3, 4, 5, 6, 7},
            {2, 3, 4, 5, 6},
            {2, 3, 4},
            {
                2: 4,
                3: 4,
                4: 4,
                5: 5,
                6: 6,
            },
            1000, 100,
            {
                0: -300,  # -3 * 100
                1: -300,  # -3 * 100
                2: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 4 // 4
                3: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 4 // 4
                4: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 4 // 4
                5: -58,  # 100 * 5 // 8 - 100 - 100 + 100 * 4 // 5
                6: -72,  # 100 * 5 // 5 - 100 - 100 + 100 * 4 // 6
                7: -300,  # -3 * 100
                8: 0,  # not active
                9: 0,  # not active
            }
        ),
        (
            3, 15,  # epochs_since_finality > 4
            {6, 7},
            {0, 1, 2, 3, 4, 5, 6, 7},
            {2, 3, 4, 5, 6},
            {2, 3, 4},
            {
                2: 4,
                3: 4,
                4: 4,
                5: 5,
                6: 6,
            },
            1000, 100,
            {
                0: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100 - (100 - 100 * 4 // 4)
                1: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100 - (100 - 100 * 4 // 4)
                2: 0,  # -(100 - 100 * 4 // 4)
                3: 0,  # -(100 - 100 * 4 // 4)
                4: 0,  # -(100 - 100 * 4 // 4)
                5: -470,  # -(100 * 2 + 1000 * 5 // 10 // 2) - (100 - 100 * 4 // 5)
                6: -1284,  # -(100 * 2 + 1000 * 5 // 10 // 2) - (2 * (100 + 1000 * 5 // 10 // 2) + 100) - (100 - 100 * 4 // 6)  # noqa: E501
                7: -1600,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100 - (2 * (100 + 1000 * 5 // 10 // 2) + 100) - (100 - 100 * 4 // 4)  # noqa: E501
                8: 0,  # not active
                9: 0,  # not active
            }
        ),
    ]
)
def test_process_rewards_and_penalties_for_finality(
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        min_attestation_inclusion_delay,
        inactivity_penalty_quotient,
        finalized_epoch,
        current_slot,
        penalized_validator_indices,
        previous_epoch_active_validator_indices,
        previous_epoch_attester_indices,
        previous_epoch_boundary_head_attester_indices,
        inclusion_distances,
        effective_balance,
        base_reward,
        expected_rewards_received,
        sample_pending_attestation_record_params,
        sample_attestation_data_params):
    validator_registry = n_validators_state.validator_registry
    for index in penalized_validator_indices:
        validator_record = validator_registry[index].copy(
            slashed_epoch=slot_to_epoch(current_slot, slots_per_epoch),
        )
        validator_registry = update_tuple_item(validator_registry, index, validator_record)
    state = n_validators_state.copy(
        slot=current_slot,
        finalized_epoch=finalized_epoch,
        validator_registry=validator_registry,
    )
    previous_total_balance = len(previous_epoch_active_validator_indices) * effective_balance

    attestation_slot = current_slot - slots_per_epoch
    inclusion_infos = {
        index: InclusionInfo(
            attestation_slot + inclusion_distances[index],
            attestation_slot,
        )
        for index in previous_epoch_attester_indices
    }

    effective_balances = {
        index: effective_balance
        for index in previous_epoch_active_validator_indices
    }

    base_rewards = {
        index: base_reward
        for index in previous_epoch_active_validator_indices
    }

    rewards_received = {
        index: 0
        for index in range(len(state.validator_registry))
    }

    prev_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH), slots_per_epoch,
    )
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
    ]

    prev_epoch_attestations = []
    for i in range(slots_per_epoch):
        committee, shard = prev_epoch_crosslink_committees[i]
        participants_bitfield = get_empty_bitfield(target_committee_size)
        for index in previous_epoch_boundary_head_attester_indices:
            if index in committee:
                participants_bitfield = set_voted(participants_bitfield, committee.index(index))
        prev_epoch_attestations.append(
            PendingAttestationRecord(**sample_pending_attestation_record_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=(prev_epoch_start_slot + i),
                    shard=shard,
                    epoch_boundary_root=get_block_root(
                        state,
                        prev_epoch_start_slot,
                        config.LATEST_BLOCK_ROOTS_LENGTH,
                    ),
                    beacon_block_root=get_block_root(
                        state,
                        (prev_epoch_start_slot + i),
                        config.LATEST_BLOCK_ROOTS_LENGTH,
                    ),
                ),
                aggregation_bitfield=participants_bitfield,
            )
        )
    state = state.copy(
        latest_attestations=prev_epoch_attestations,
    )

    rewards_received = _process_rewards_and_penalties_for_finality(
        state,
        config,
        previous_epoch_active_validator_indices,
        previous_total_balance,
        prev_epoch_attestations,
        previous_epoch_attester_indices,
        inclusion_infos,
        effective_balances,
        base_rewards,
        rewards_received,
    )

    for index, reward_received in rewards_received.items():
        assert reward_received == expected_rewards_received[index]


@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'attestation_inclusion_reward_quotient,'
        'current_slot,'
        'previous_epoch_attester_indices,'
        'inclusion_slots,'
        'base_reward,'
        'expected_rewards_received'
    ),
    [
        (
            20,
            10,
            2,
            10,
            4,
            40,
            {2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 15, 16, 17},
            {
                2: 31,  # proposer index for inclusion slot 31: 6
                3: 31,
                4: 32,  # proposer index for inclusion slot 32: 19
                5: 32,
                6: 32,
                9: 35,  # proposer index for inclusion slot 35: 16
                10: 35,
                11: 35,
                12: 35,
                13: 35,
                15: 38,  # proposer index for inclusion slot 38: 1
                16: 38,
                17: 38,
            },
            100,
            {
                0: 0,
                1: 75,  # 3 * (100 // 4)
                2: 0,
                3: 0,
                4: 0,
                5: 0,
                6: 50,  # 2 * (100 // 4)
                7: 0,
                8: 0,
                9: 0,
                10: 0,
                11: 0,
                12: 0,
                13: 0,
                14: 0,
                15: 0,
                16: 125,  # 5 * (100 // 4)
                17: 0,
                18: 0,
                19: 75,  # 3 * (100 // 4)
            }
        ),
    ]
)
def test_process_rewards_and_penalties_for_attestation_inclusion(
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        attestation_inclusion_reward_quotient,
        current_slot,
        previous_epoch_attester_indices,
        inclusion_slots,
        base_reward,
        expected_rewards_received):
    state = n_validators_state.copy(
        slot=current_slot,
    )
    inclusion_infos = {
        index: InclusionInfo(
            inclusion_slots[index],
            inclusion_slots[index] - config.MIN_ATTESTATION_INCLUSION_DELAY,
        )
        for index in previous_epoch_attester_indices
    }

    base_rewards = {
        index: base_reward
        for index in previous_epoch_attester_indices
    }

    rewards_received = {
        index: 0
        for index in range(len(n_validators_state.validator_registry))
    }

    # Process the rewards and penalties for attestation inclusion
    rewards_received = _process_rewards_and_penalties_for_attestation_inclusion(
        state,
        config,
        previous_epoch_attester_indices,
        inclusion_infos,
        base_rewards,
        rewards_received,
    )

    for index, reward_received in rewards_received.items():
        assert reward_received == expected_rewards_received[index]


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'current_slot,'
        'num_attesting_validators'
    ),
    [
        (
            50,
            10,
            5,
            10,
            100,
            3,
        ),
        (
            50,
            10,
            5,
            10,
            100,
            4,
        ),
    ]
)
def test_process_rewards_and_penalties_for_crosslinks(
        random,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        current_slot,
        num_attesting_validators,
        max_deposit_amount,
        min_attestation_inclusion_delay,
        sample_attestation_data_params,
        sample_pending_attestation_record_params):
    previous_epoch = current_slot // slots_per_epoch - 1
    state = n_validators_state.copy(
        slot=current_slot,
    )
    # Compute previous epoch committees
    prev_epoch_start_slot = get_epoch_start_slot(previous_epoch, slots_per_epoch)
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
    ]

    # Record which validators attest during each slot for reward collation.
    each_slot_attestion_validators_list = []

    previous_epoch_attestations = []
    for i in range(slots_per_epoch):
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
        data_slot = i + previous_epoch * slots_per_epoch
        previous_epoch_attestations.append(
            PendingAttestationRecord(**sample_pending_attestation_record_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=data_slot,
                    shard=shard,
                ),
                aggregation_bitfield=participants_bitfield,
                slot_included=(data_slot + min_attestation_inclusion_delay),
            )
        )

    active_validators = set(
        [
            i for i in range(len(state.validator_registry))
        ]
    )

    effective_balances = {
        index: get_effective_balance(
            state.validator_balances,
            index,
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in active_validators
    }

    validator_balance = max_deposit_amount
    total_active_balance = len(active_validators) * validator_balance

    _base_reward_quotient = (
        integer_squareroot(total_active_balance) // config.BASE_REWARD_QUOTIENT
    )
    base_rewards = {
        index: get_base_reward(
            state=state,
            index=index,
            base_reward_quotient=_base_reward_quotient,
            max_deposit_amount=max_deposit_amount,
        )
        for index in active_validators
    }

    rewards_received = {
        index: 0
        for index in range(len(state.validator_registry))
    }

    rewards_received = _process_rewards_and_penalties_for_crosslinks(
        state,
        config,
        tuple(previous_epoch_attestations),
        effective_balances,
        base_rewards,
        rewards_received,
    )

    expected_rewards_received = {
        index: 0
        for index in range(len(state.validator_registry))
    }
    for i in range(slots_per_epoch):
        crosslink_committee, shard = prev_epoch_crosslink_committees[i]
        attesting_validators = each_slot_attestion_validators_list[i]
        total_attesting_balance = len(attesting_validators) * validator_balance
        total_committee_balance = len(crosslink_committee) * validator_balance
        _base_reward_quotient = (
            integer_squareroot(total_active_balance) // config.BASE_REWARD_QUOTIENT
        )
        for index in attesting_validators:
            reward = get_base_reward(
                state=state,
                index=index,
                base_reward_quotient=_base_reward_quotient,
                max_deposit_amount=max_deposit_amount,
            ) * total_attesting_balance // total_committee_balance
            expected_rewards_received[index] += reward
        for index in set(crosslink_committee).difference(attesting_validators):
            penalty = get_base_reward(
                state=state,
                index=index,
                base_reward_quotient=_base_reward_quotient,
                max_deposit_amount=max_deposit_amount,
            )
            expected_rewards_received[index] -= penalty

    # Check the rewards/penalties match
    for index, reward_received in rewards_received.items():
        assert rewards_received[index] == expected_rewards_received[index]


#
# Validator registry and shuffling seed data
#
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


#
# Final updates
#
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
