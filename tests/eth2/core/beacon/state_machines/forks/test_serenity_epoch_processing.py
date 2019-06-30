import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    assoc,
    curry,
)
import ssz

from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2._utils.bitfield import (
    set_voted,
    get_empty_bitfield,
)
from eth2._utils.hash import (
    hash_eth2,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committee,
    get_epoch_committee_count,
    get_epoch_start_shard,
    get_shard_delta,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
    GWEI_PER_ETH,
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
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.typing import Gwei
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _bft_threshold_met,
    _is_epoch_justifiable,
    _determine_new_finalized_epoch,
    get_delayed_activation_exit_epoch,
    process_crosslinks,
    process_final_updates,
    process_justification_and_finalization,
    process_slashings,
)

from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator


@pytest.mark.parametrize(
    "total_balance,"
    "attesting_balance,"
    "expected,",
    (
        (
            1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, True,
        ),
        (
            1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, False,
        ),
    )
)
def test_bft_threshold_met(attesting_balance,
                           total_balance,
                           expected):
    assert _bft_threshold_met(attesting_balance, total_balance) == expected


@pytest.mark.parametrize(
    "justification_bitfield,"
    "previous_justified_epoch,"
    "current_justified_epoch,"
    "expected,",
    (
        # Rule 1
        (0b111110, 3, 3, 3),
        # Rule 2
        (0b111110, 4, 4, 4),
        # Rule 3
        (0b110111, 3, 4, 4),
        # Rule 4
        (0b110011, 2, 5, 5),
        # No finalize
        (0b110000, 2, 2, 1),
    )
)
def test_get_finalized_epoch(justification_bitfield,
                             previous_justified_epoch,
                             current_justified_epoch,
                             expected):
    current_epoch = 6
    finalized_epoch = 1
    assert _determine_new_finalized_epoch(
        finalized_epoch,
        previous_justified_epoch,
        current_justified_epoch,
        current_epoch,
        justification_bitfield,
    ) == expected


def test_justification_without_mock(genesis_state,
                                    slots_per_historical_root,
                                    config):

    state = genesis_state
    state = process_justification_and_finalization(state, config)
    assert state.justification_bitfield == 0b0


def _mk_pending_attestation(block_root, epoch, shard, bitfield):
    return PendingAttestation(
        aggregation_bitfield=bitfield,
        data=AttestationData(
            target_epoch=epoch,
            target_root=block_root,
            crosslink=Crosslink(
                shard=shard,
            )
        ),
    )


# TODO(ralexstokes) move to tools/builder
@to_tuple
def _mk_all_pending_attestations_with_full_participation_in_epoch(state,
                                                                  epoch,
                                                                  config):
    block_root = get_block_root(
        state,
        epoch,
        config.SLOTS_PER_EPOCH,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    epoch_start_shard = get_epoch_start_shard(
        state,
        epoch,
        CommitteeConfig(config),
    )
    shard_delta = get_shard_delta(
        state,
        epoch,
        CommitteeConfig(config),
    )
    for shard in range(epoch_start_shard, epoch_start_shard + shard_delta):
        crosslink_committee = get_crosslink_committee(
            state,
            epoch,
            shard,
            CommitteeConfig(config),
        )
        if not crosslink_committee:
            continue

        bitfield = get_empty_bitfield(len(crosslink_committee))
        for i in range(len(crosslink_committee)):
            bitfield = set_voted(bitfield, i)

        yield _mk_pending_attestation(
            block_root,
            epoch,
            shard,
            bitfield,
        )


@pytest.mark.parametrize(
    (
        "current_epoch",
        "current_epoch_justifiable",
        "previous_epoch_justifiable",
        "previous_justified_epoch",
        "current_justified_epoch",
        "justification_bitfield",
        "finalized_epoch",
        "justified_epoch_after",
        "justification_bitfield_after",
        "finalized_epoch_after",
    ),
    (
        # No processing on first and second epochs
        (0, True, False, 0, 0, 0b0, 0, 0, 0b0, 0),
        (1, True, True, 0, 0, 0b1, 0, 0, 0b1, 0),
        # Trigger R4 to finalize epoch 1
        (2, True, True, 0, 1, 0b11, 0, 2, 0b111, 1),  # R4 finalize 1
        # Trigger R2 to finalize epoch 1
        # Trigger R3 to finalize epoch 2
        (2, False, True, 0, 1, 0b11, 0, 1, 0b110, 0),  # R2 finalize 0
        (3, False, True, 1, 1, 0b110, 0, 2, 0b1110, 1),  # R2 finalize 1
        (4, True, True, 1, 2, 0b1110, 1, 4, 0b11111, 2),  # R3 finalize 2
        # Trigger R1 to finalize epoch 2
        (2, False, True, 0, 1, 0b11, 0, 1, 0b110, 0),  # R2 finalize 0
        (3, False, True, 1, 1, 0b110, 0, 2, 0b1110, 1),  # R2 finalize 1
        (4, False, True, 1, 2, 0b1110, 1, 3, 0b11110, 1),  # R1 finalize 1
        (5, False, True, 2, 3, 0b11110, 1, 4, 0b111110, 2),  # R1 finalize 2
    ),
)
def test_process_justification_and_finalization(genesis_state,
                                                current_epoch,
                                                current_epoch_justifiable,
                                                previous_epoch_justifiable,
                                                previous_justified_epoch,
                                                current_justified_epoch,
                                                justification_bitfield,
                                                finalized_epoch,
                                                justified_epoch_after,
                                                justification_bitfield_after,
                                                finalized_epoch_after,
                                                config):
    previous_epoch = max(current_epoch - 1, 0)
    slot = (current_epoch + 1) * config.SLOTS_PER_EPOCH - 1

    state = genesis_state.copy(
        slot=slot,
        previous_justified_epoch=previous_justified_epoch,
        current_justified_epoch=current_justified_epoch,
        justification_bitfield=justification_bitfield,
        finalized_epoch=finalized_epoch,
        block_roots=tuple(
            i.to_bytes(32, "little")
            for i in range(config.SLOTS_PER_HISTORICAL_ROOT)
        ),
    )

    if previous_epoch_justifiable:
        attestations = _mk_all_pending_attestations_with_full_participation_in_epoch(
            state,
            previous_epoch,
            config,
        )
        state = state.copy(
            previous_epoch_attestations=attestations,
        )

    if current_epoch_justifiable:
        attestations = _mk_all_pending_attestations_with_full_participation_in_epoch(
            state,
            current_epoch,
            config,
        )
        state = state.copy(
            current_epoch_attestations=attestations,
        )

    post_state = process_justification_and_finalization(state, config)

    assert post_state.previous_justified_epoch == state.current_justified_epoch
    assert post_state.current_justified_epoch == justified_epoch_after
    assert post_state.justification_bitfield == justification_bitfield_after
    assert post_state.finalized_epoch == finalized_epoch_after


#
# Crosslink
#
# TODO(ralexstokes) fix test
# @settings(max_examples=1)
# @given(random=st.randoms())
# @pytest.mark.parametrize(
#     (
#         'n,'
#         'slots_per_epoch,'
#         'target_committee_size,'
#         'shard_count,'
#     ),
#     [
#         (
#             90,
#             10,
#             9,
#             10,
#         ),
#     ]
# )
# @pytest.mark.parametrize(
#     (
#         'success_crosslink_in_previous_epoch,'
#         'success_crosslink_in_current_epoch,'
#     ),
#     [
#         (
#             False,
#             False,
#         ),
#         (
#             True,
#             False,
#         ),
#         (
#             False,
#             True,
#         ),
#     ]
# )
# def test_process_crosslinks(
#         random,
#         genesis_state,
#         config,
#         slots_per_epoch,
#         target_committee_size,
#         shard_count,
#         success_crosslink_in_previous_epoch,
#         success_crosslink_in_current_epoch,
#         sample_attestation_data_params,
#         sample_pending_attestation_record_params):
#     shard = 1
#     previous_epoch_crosslink_data_root = hash_eth2(b'previous_epoch_crosslink_data_root')
#     current_epoch_crosslink_data_root = hash_eth2(b'current_epoch_crosslink_data_root')
#     current_slot = config.SLOTS_PER_EPOCH * 2 - 1

#     genesis_crosslinks = tuple([
#         Crosslink(
#             shard=shard,
#         )
#         for shard in range(shard_count)
#     ])
#     state = genesis_state.copy(
#         slot=current_slot,
#         latest_crosslinks=genesis_crosslinks,
#     )

#     # Generate previous epoch attestations
#     current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
#     previous_epoch = current_epoch - 1
#     previous_epoch_start_slot = get_epoch_start_slot(previous_epoch, config.SLOTS_PER_EPOCH)
#     current_epoch_start_slot = get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
#     previous_epoch_attestations = []
#     for slot_in_previous_epoch in range(previous_epoch_start_slot, current_epoch_start_slot):
#         if len(previous_epoch_attestations) > 0:
#             break
#         for committee, _shard in get_crosslink_committees_at_slot(
#             state,
#             slot_in_previous_epoch,
#             CommitteeConfig(config),
#         ):
#             if _shard == shard:
#                 # Sample validators attesting to this shard.
#                 # if `success_crosslink_in_previous_epoch` is True, have >2/3 committee attest
#                 if success_crosslink_in_previous_epoch:
#                     attesting_validators = random.sample(committee, (2 * len(committee) // 3 + 1))
#                 else:
#                     attesting_validators = random.sample(committee, (2 * len(committee) // 3 - 1))
#                 # Generate the bitfield
#                 aggregation_bitfield = get_empty_bitfield(len(committee))
#                 for v_index in attesting_validators:
#                     aggregation_bitfield = set_voted(
#                         aggregation_bitfield, committee.index(v_index))
#                 # Generate the attestation
#                 previous_epoch_attestations.append(
#                     PendingAttestation(**sample_pending_attestation_record_params).copy(
#                         aggregation_bitfield=aggregation_bitfield,
#                         data=AttestationData(**sample_attestation_data_params).copy(
#                             slot=slot_in_previous_epoch,
#                             shard=shard,
#                             crosslink_data_root=previous_epoch_crosslink_data_root,
#                             previous_crosslink=Crosslink(
#                                 shard=shard,
#                             ),
#                         ),
#                     )
#                 )

#     # Generate current epoch attestations
#     next_epoch_start_slot = current_epoch_start_slot + config.SLOTS_PER_EPOCH
#     current_epoch_attestations = []
#     for slot_in_current_epoch in range(current_epoch_start_slot, next_epoch_start_slot):
#         if len(current_epoch_attestations) > 0:
#             break
#         for committee, _shard in get_crosslink_committees_at_slot(
#             state,
#             slot_in_current_epoch,
#             CommitteeConfig(config),
#         ):
#             if _shard == shard:
#                 # Sample validators attesting to this shard.
#                 # if `success_crosslink_in_current_epoch` is True, have >2/3 committee attest
#                 if success_crosslink_in_current_epoch:
#                     attesting_validators = random.sample(committee, (2 * len(committee) // 3 + 1))
#                 else:
#                     attesting_validators = random.sample(committee, (2 * len(committee) // 3 - 1))
#                 # Generate the bitfield
#                 aggregation_bitfield = get_empty_bitfield(len(committee))
#                 for v_index in attesting_validators:
#                     aggregation_bitfield = set_voted(
#                         aggregation_bitfield, committee.index(v_index))
#                 # Generate the attestation
#                 current_epoch_attestations.append(
#                     PendingAttestation(**sample_pending_attestation_record_params).copy(
#                         aggregation_bitfield=aggregation_bitfield,
#                         data=AttestationData(**sample_attestation_data_params).copy(
#                             slot=slot_in_current_epoch,
#                             shard=shard,
#                             crosslink_data_root=current_epoch_crosslink_data_root,
#                             previous_crosslink=Crosslink(
#                                 shard=shard,
#                             ),
#                         ),
#                     )
#                 )

#     state = state.copy(
#         previous_epoch_attestations=previous_epoch_attestations,
#         current_epoch_attestations=current_epoch_attestations,
#     )
#     assert (state.latest_crosslinks[shard].epoch == config.GENESIS_EPOCH and
#             state.latest_crosslinks[shard].crosslink_data_root == ZERO_HASH32)

#     new_state = process_crosslinks(state, config)
#     crosslink_record = new_state.latest_crosslinks[shard]
#     if success_crosslink_in_current_epoch:
#         attestation = current_epoch_attestations[0]
#         assert (crosslink_record.epoch == current_epoch and
#                 crosslink_record.crosslink_data_root == attestation.data.crosslink_data_root and
#                 attestation.data.crosslink_data_root == current_epoch_crosslink_data_root)
#     elif success_crosslink_in_previous_epoch:
#         attestation = previous_epoch_attestations[0]
#         assert (crosslink_record.epoch == current_epoch and
#                 crosslink_record.crosslink_data_root == attestation.data.crosslink_data_root and
#                 attestation.data.crosslink_data_root == previous_epoch_crosslink_data_root)
#     else:
#         assert (crosslink_record.epoch == config.GENESIS_EPOCH and
#                 crosslink_record.crosslink_data_root == ZERO_HASH32)


#
# Rewards and penalties
#
# @pytest.mark.parametrize(
#     (
#         'n,'
#         'slots_per_epoch,'
#         'target_committee_size,'
#         'shard_count,'
#         'min_attestation_inclusion_delay,'
#         'attestation_inclusion_reward_quotient,'
#         'inactivity_penalty_quotient,'
#         'genesis_slot,'
#     ),
#     [
#         (
#             15,
#             3,
#             5,
#             3,
#             1,
#             4,
#             10,
#             0,
#         )
#     ]
# )
# @pytest.mark.parametrize(
#     (
#         'finalized_epoch,current_slot,'
#         'penalized_validator_indices,'
#         'previous_epoch_active_validator_indices,'
#         'previous_epoch_attester_indices,'
#         'previous_epoch_boundary_head_attester_indices,'
#         'inclusion_distances,'
#         'effective_balance,base_reward,'
#         'expected_rewards_received'
#     ),
#     [
#         (
#             4, 15,  # epochs_since_finality <= 4
#             {8, 9},
#             {0, 1, 2, 3, 4, 5, 6, 7},
#             {2, 3, 4, 5, 6},
#             {2, 3, 4},
#             {
#                 2: 1,
#                 3: 1,
#                 4: 1,
#                 5: 2,
#                 6: 3,
#             },
#             1000, 100,
#             {
#                 0: -300,  # -3 * 100
#                 1: -275,  # -3 * 100 + 1 * 100 // 4
#                 2: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
#                 3: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
#                 4: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
#                 5: -63,  # 100 * 5 // 8 - 100 - 100 + 100 * 1 // 2 + 1 * 100 // 4
#                 6: -105,  # 100 * 5 // 8 - 100 - 100 + 100 * 1 // 3
#                 7: -300,  # -3 * 100
#                 8: 0,
#                 9: 0,
#                 10: 0,
#                 11: 0,
#                 12: 75,  # 3 * 100 // 4
#                 13: 0,
#                 14: 0,
#             }
#         ),
#         (
#             3, 23,  # epochs_since_finality > 4
#             {8, 9},
#             {0, 1, 2, 3, 4, 5, 6, 7},
#             {2, 3, 4, 5, 6},
#             {2, 3, 4},
#             {
#                 2: 1,
#                 3: 1,
#                 4: 1,
#                 5: 2,
#                 6: 3,
#             },
#             1000, 100,
#             {
#                 0: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
#                 1: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
#                 2: 0,  # -(100 - 100 * 1 // 1)
#                 3: 0,  # -(100 - 100 * 1 // 1)
#                 4: 0,  # -(100 - 100 * 1 // 1)
#                 5: -500,  # -(100 - 100 * 1 // 2) - (100 * 2 + 1000 * 5 // 10 // 2)
#                 6: -517,  # -(100 - 100 * 1 // 3) - (100 * 2 + 1000 * 5 // 10 // 2)
#                 7: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
#                 8: -800,  # -(2 * (100 + 1000 * 5 // 10 // 2) + 100)
#                 9: -800,  # -(2 * (100 + 1000 * 5 // 10 // 2) + 100)
#                 10: 0,
#                 11: 0,
#                 12: 0,
#                 13: 0,
#                 14: 0,
#             }
#         ),
#     ]
# )
# def test_process_rewards_and_penalties_for_finality(
#         monkeypatch,
#         genesis_state,
#         config,
#         slots_per_epoch,
#         target_committee_size,
#         shard_count,
#         min_attestation_inclusion_delay,
#         inactivity_penalty_quotient,
#         finalized_epoch,
#         current_slot,
#         penalized_validator_indices,
#         previous_epoch_active_validator_indices,
#         previous_epoch_attester_indices,
#         previous_epoch_boundary_head_attester_indices,
#         inclusion_distances,
#         effective_balance,
#         base_reward,
#         expected_rewards_received,
#         sample_pending_attestation_record_params,
#         sample_attestation_data_params):
#     # Mock `get_beacon_proposer_index
#     from eth2.beacon.state_machines.forks.serenity import epoch_processing

#     def mock_get_beacon_proposer_index(state,
#                                        slot,
#                                        committee_config,
#                                        registry_change=False):
#         mock_proposer_for_slot = {
#             13: 12,
#             14: 5,
#             15: 1,
#         }
#         return mock_proposer_for_slot[slot]

#     monkeypatch.setattr(
#         epoch_processing,
#         'get_beacon_proposer_index',
#         mock_get_beacon_proposer_index
#     )

#     validators = genesis_state.validators
#     for index in penalized_validator_indices:
#         validator_record = validators[index].copy(
#             slashed=True,
#         )
#         validators = update_tuple_item(validators, index, validator_record)
#     state = genesis_state.copy(
#         slot=current_slot,
#         finalized_epoch=finalized_epoch,
#         validators=validators,
#     )
#     previous_total_balance = len(previous_epoch_active_validator_indices) * effective_balance

#     attestation_slot = current_slot - slots_per_epoch
#     inclusion_infos = {
#         index: InclusionInfo(
#             attestation_slot + inclusion_distances[index],
#             attestation_slot,
#         )
#         for index in previous_epoch_attester_indices
#     }

#     effective_balances = {
#         index: effective_balance
#         for index in range(len(state.validators))
#     }

#     base_rewards = {
#         index: base_reward
#         for index in range(len(state.validators))
#     }

#     prev_epoch_start_slot = get_epoch_start_slot(
#         state.previous_epoch(config.SLOTS_PER_EPOCH), slots_per_epoch,
#     )
#     prev_epoch_crosslink_committees = [
#         get_crosslink_committees_at_slot(
#             state,
#             slot,
#             CommitteeConfig(config),
#         )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
#     ]

#     prev_epoch_attestations = []
#     for i in range(slots_per_epoch):
#         committee, shard = prev_epoch_crosslink_committees[i]
#         participants_bitfield = get_empty_bitfield(target_committee_size)
#         for index in previous_epoch_boundary_head_attester_indices:
#             if index in committee:
#                 participants_bitfield = set_voted(participants_bitfield, committee.index(index))
#         prev_epoch_attestations.append(
#             PendingAttestation(**sample_pending_attestation_record_params).copy(
#                 aggregation_bitfield=participants_bitfield,
#                 data=AttestationData(**sample_attestation_data_params).copy(
#                     slot=(prev_epoch_start_slot + i),
#                     shard=shard,
#                     target_root=get_block_root(
#                         state,
#                         prev_epoch_start_slot,
#                         config.SLOTS_PER_HISTORICAL_ROOT,
#                     ),
#                     beacon_block_root=get_block_root(
#                         state,
#                         (prev_epoch_start_slot + i),
#                         config.SLOTS_PER_HISTORICAL_ROOT,
#                     ),
#                 ),
#             )
#         )
#     state = state.copy(
#         previous_epoch_attestations=prev_epoch_attestations,
#     )

#     rewards_received, penalties_received = _process_rewards_and_penalties_for_finality(
#         state,
#         config,
#         previous_epoch_active_validator_indices,
#         previous_total_balance,
#         prev_epoch_attestations,
#         previous_epoch_attester_indices,
#         inclusion_infos,
#         effective_balances,
#         base_rewards,
#     )

#     for index in range(len(state.validators)):
#         assert (
#             rewards_received[index] - penalties_received[index] == expected_rewards_received[index]
#         )


# @settings(max_examples=1)
# @given(random=st.randoms())
# @pytest.mark.parametrize(
#     (
#         'n,'
#         'slots_per_epoch,'
#         'target_committee_size,'
#         'shard_count,'
#         'current_slot,'
#         'num_attesting_validators,'
#         'genesis_slot,'
#     ),
#     [
#         (
#             50,
#             10,
#             5,
#             10,
#             100,
#             3,
#             0,
#         ),
#         (
#             50,
#             10,
#             5,
#             10,
#             100,
#             4,
#             0,
#         ),
#     ]
# )
# def test_process_rewards_and_penalties_for_crosslinks(
#         random,
#         genesis_state,
#         config,
#         slots_per_epoch,
#         target_committee_size,
#         shard_count,
#         current_slot,
#         num_attesting_validators,
#         max_effective_balance,
#         min_attestation_inclusion_delay,
#         sample_attestation_data_params,
#         sample_pending_attestation_record_params):
#     previous_epoch = current_slot // slots_per_epoch - 1
#     state = genesis_state.copy(
#         slot=current_slot,
#     )
#     # Compute previous epoch committees
#     prev_epoch_start_slot = get_epoch_start_slot(previous_epoch, slots_per_epoch)
#     prev_epoch_crosslink_committees = [
#         get_crosslink_committees_at_slot(
#             state,
#             slot,
#             CommitteeConfig(config),
#         )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
#     ]

#     # Record which validators attest during each slot for reward collation.
#     each_slot_attestion_validators_list = []

#     previous_epoch_attestations = []
#     for i in range(slots_per_epoch):
#         committee, shard = prev_epoch_crosslink_committees[i]
#         # Randomly sample `num_attesting_validators` validators
#         # from the committee to attest in this slot.
#         crosslink_data_root_attesting_validators = random.sample(
#             committee,
#             num_attesting_validators,
#         )
#         each_slot_attestion_validators_list.append(crosslink_data_root_attesting_validators)
#         participants_bitfield = get_empty_bitfield(target_committee_size)
#         for index in crosslink_data_root_attesting_validators:
#             participants_bitfield = set_voted(participants_bitfield, committee.index(index))
#         data_slot = i + previous_epoch * slots_per_epoch
#         previous_epoch_attestations.append(
#             PendingAttestation(**sample_pending_attestation_record_params).copy(
#                 aggregation_bitfield=participants_bitfield,
#                 data=AttestationData(**sample_attestation_data_params).copy(
#                     slot=data_slot,
#                     shard=shard,
#                     previous_crosslink=Crosslink(
#                         shard=shard
#                     ),
#                 ),
#                 inclusion_slot=(data_slot + min_attestation_inclusion_delay),
#             )
#         )
#     state = state.copy(
#         previous_epoch_attestations=tuple(previous_epoch_attestations),
#     )

#     active_validators = set(
#         [
#             i for i in range(len(state.validators))
#         ]
#     )

#     effective_balances = {
#         index: state.validators[index].effective_balance
#         for index in active_validators
#     }

#     validator_balance = max_effective_balance
#     total_active_balance = len(active_validators) * validator_balance

#     base_rewards = {
#         index: get_base_reward(
#             state=state,
#             index=index,
#             base_reward_quotient=config.BASE_REWARD_QUOTIENT,
#             previous_total_balance=total_active_balance,
#             max_effective_balance=max_effective_balance,
#         )
#         for index in active_validators
#     }

#     rewards_received, penalties_received = _process_rewards_and_penalties_for_crosslinks(
#         state,
#         config,
#         effective_balances,
#         base_rewards,
#     )

#     expected_rewards_received = {
#         index: 0
#         for index in range(len(state.validators))
#     }
#     for i in range(slots_per_epoch):
#         crosslink_committee, shard = prev_epoch_crosslink_committees[i]
#         attesting_validators = each_slot_attestion_validators_list[i]
#         total_attesting_balance = len(attesting_validators) * validator_balance
#         total_committee_balance = len(crosslink_committee) * validator_balance
#         for index in attesting_validators:
#             reward = get_base_reward(
#                 state=state,
#                 index=index,
#                 base_reward_quotient=config.BASE_REWARD_QUOTIENT,
#                 previous_total_balance=total_active_balance,
#                 max_effective_balance=max_effective_balance,
#             ) * total_attesting_balance // total_committee_balance
#             expected_rewards_received[index] += reward
#         for index in set(crosslink_committee).difference(attesting_validators):
#             penalty = get_base_reward(
#                 state=state,
#                 index=index,
#                 base_reward_quotient=config.BASE_REWARD_QUOTIENT,
#                 previous_total_balance=total_active_balance,
#                 max_effective_balance=max_effective_balance,
#             )
#             expected_rewards_received[index] -= penalty

#     # Check the rewards/penalties match
#     for index in range(len(state.validators)):
#         assert (
#             rewards_received[index] - penalties_received[index] == expected_rewards_received[index]
#         )


#
# Ejections
#
def test_process_ejections(genesis_state, config, activation_exit_delay):
    current_epoch = 8
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH),
    )
    delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(
        current_epoch,
        activation_exit_delay,
    )

    ejecting_validator_index = 0
    validator = state.validators[ejecting_validator_index]
    assert validator.is_active(current_epoch)
    assert validator.exit_epoch > delayed_activation_exit_epoch

    state = state.update_validator_balance(
        validator_index=ejecting_validator_index,
        balance=config.EJECTION_BALANCE - 1,
    )
    result_state = process_ejections(state, config)
    result_validator = result_state.validators[ejecting_validator_index]
    assert result_validator.is_active(current_epoch)
    assert result_validator.exit_epoch == delayed_activation_exit_epoch
    # The ejecting validator will be inactive at the exit_epoch
    assert not result_validator.is_active(result_validator.exit_epoch)
    # Other validators are not ejected
    assert (
        result_state.validators[ejecting_validator_index + 1].exit_epoch ==
        FAR_FUTURE_EPOCH
    )


#
# Validator registry and shuffling seed data
#
# @pytest.mark.parametrize(
#     (
#         'validator_count, slots_per_epoch, target_committee_size, shard_count, state_slot,'
#         'validators_update_epoch,'
#         'finalized_epoch,'
#         'has_crosslink,'
#         'crosslink_epoch,'
#         'expected_need_to_update,'
#     ),
#     [
#         # state.finalized_epoch <= state.validators_update_epoch
#         (
#             40, 4, 2, 2, 16,
#             4, 4, False, 0, False
#         ),
#         # state.latest_crosslinks[shard].epoch <= state.validators_update_epoch
#         (
#             40, 4, 2, 2, 16,
#             4, 8, True, 4, False,
#         ),
#         # state.finalized_epoch > state.validators_update_epoch and
#         # state.latest_crosslinks[shard].epoch > state.validators_update_epoch
#         (
#             40, 4, 2, 2, 16,
#             4, 8, True, 6, True,
#         ),
#     ]
# )
# def test_check_if_update_validators(genesis_state,
#                                     state_slot,
#                                     validators_update_epoch,
#                                     finalized_epoch,
#                                     has_crosslink,
#                                     crosslink_epoch,
#                                     expected_need_to_update,
#                                     config):
#     state = genesis_state.copy(
#         slot=state_slot,
#         finalized_epoch=finalized_epoch,
#         validators_update_epoch=validators_update_epoch,
#     )
#     if has_crosslink:
#         state = state.copy(
#             latest_crosslinks=tuple(
#                 Crosslink(
#                     shard=shard,
#                 ) for shard in range(config.SHARD_COUNT)
#             ),
#         )

#     need_to_update, num_shards_in_committees = _check_if_update_validators(state, config)

#     assert need_to_update == expected_need_to_update
#     if expected_need_to_update:
#         expected_num_shards_in_committees = get_current_epoch_committee_count(
#             state,
#             shard_count=config.SHARD_COUNT,
#             slots_per_epoch=config.SLOTS_PER_EPOCH,
#             target_committee_size=config.TARGET_COMMITTEE_SIZE,
#         )
#         assert num_shards_in_committees == expected_num_shards_in_committees
#     else:
#         assert num_shards_in_committees == 0


@pytest.mark.parametrize(
    (
        'n',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (
            10,
            10,
            9,
            10,
        ),
    ]
)
def test_update_validators(n,
                           genesis_state,
                           config,
                           slots_per_epoch):
    validators = list(genesis_state.validators)
    activating_index = n
    exiting_index = 0

    activating_validator = Validator.create_pending_validator(
        pubkey=b'\x10' * 48,
        withdrawal_credentials=b'\x11' * 32,
        amount=Gwei(32 * GWEI_PER_ETH),
        config=config,
    )

    exiting_validator = genesis_state.validators[exiting_index].copy(
        exit_epoch=FAR_FUTURE_EPOCH,
    )

    validators[exiting_index] = exiting_validator
    validators.append(activating_validator)
    state = genesis_state.copy(
        validators=validators,
        balances=genesis_state.balances + (config.MAX_EFFECTIVE_BALANCE,),
    )

    state = update_validators(state, config)

    entry_exit_effect_epoch = get_delayed_activation_exit_epoch(
        state.current_epoch(slots_per_epoch),
        config.ACTIVATION_EXIT_DELAY,
    )

    # Check if the activating_validator is activated
    assert state.validators[activating_index].activation_epoch == entry_exit_effect_epoch
    # Check if the activating_validator is exited
    assert state.validators[exiting_index].exit_epoch == entry_exit_effect_epoch


@pytest.mark.parametrize(
    (
        'validator_count, slots_per_epoch, target_committee_size, shard_count,'
        'epochs_per_historical_vector, min_seed_lookahead, state_slot,'
        'need_to_update,'
        'num_shards_in_committees,'
        'validators_update_epoch,'
        'epochs_since_last_registry_change_is_power_of_two,'
        'current_shuffling_epoch,'
        'randao_mixes,'
        'expected_current_shuffling_epoch,'
    ),
    [
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            2,
            True,  # (state.current_epoch - state.validators_update_epoch) is power of two
            0,
            [i.to_bytes(32, 'little') for i in range(2**10)],
            5,  # expected current_shuffling_epoch is state.next_epoch
        ),
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            1,
            False,  # (state.current_epoch - state.validators_update_epoch) != power of two
            0,
            [i.to_bytes(32, 'little') for i in range(2**10)],
            0,  # expected_current_shuffling_epoch is current_shuffling_epoch because it will not be updated  # noqa: E501
        ),
    ]
)
def test_process_validators(monkeypatch,
                            genesis_state,
                            slots_per_epoch,
                            state_slot,
                            need_to_update,
                            num_shards_in_committees,
                            validators_update_epoch,
                            epochs_since_last_registry_change_is_power_of_two,
                            current_shuffling_epoch,
                            randao_mixes,
                            expected_current_shuffling_epoch,
                            activation_exit_delay,
                            config):
    # Mock check_if_update_validators
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_check_if_update_validators(state, config):
        return need_to_update, num_shards_in_committees

    monkeypatch.setattr(
        epoch_processing,
        '_check_if_update_validators',
        mock_check_if_update_validators
    )

    # Mock generate_seed
    new_seed = b'\x88' * 32

    def mock_generate_seed(state,
                           epoch,
                           committee_config):
        return new_seed

    monkeypatch.setattr(
        'eth2.beacon.helpers.generate_seed',
        mock_generate_seed
    )

    # Set state
    state = genesis_state.copy(
        slot=state_slot,
        validators_update_epoch=validators_update_epoch,
        current_shuffling_epoch=current_shuffling_epoch,
        randao_mixes=randao_mixes,
    )

    result_state = process_validators(state, config)

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
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'epochs_per_slashed_balances_vector',
        'slashed_balances',
        'expected_total_penalties',
    ),
    [
        (4, 8, 8, 8, (30, 10) + (0,) * 6, 30 - 10)
    ]
)
def test_compute_total_penalties(genesis_state,
                                 config,
                                 slots_per_epoch,
                                 current_epoch,
                                 slashed_balances,
                                 expected_total_penalties):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
        slashed_balances=slashed_balances,
    )
    total_penalties = _compute_total_penalties(
        state,
        config,
        current_epoch,
    )
    assert total_penalties == expected_total_penalties


@pytest.mark.parametrize(
    (
        'validator_count',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'epochs_per_slashed_balances_vector',
    ),
    [
        (
            10, 4, 8, 8, 8,
        )
    ]
)
@pytest.mark.parametrize(
    (
        'total_penalties',
        'total_balance',
        'min_slashing_penalty_quotient',
        'expected_penalty',
    ),
    [
        (
            10**9,  # 1 ETH
            (32 * 10**9 * 10),
            2**5,
            # effective_balance // MIN_SLASHING_PENALTY_QUOTIENT,
            32 * 10**9 // 2**5,
        ),
        (
            10**9,  # 1 ETH
            (32 * 10**9 * 10),
            2**10,  # Make MIN_SLASHING_PENALTY_QUOTIENT greater
            # effective_balance * min(total_penalties * 3, total_balance) // total_balance,
            32 * 10**9 * min(10**9 * 3, (32 * 10**9 * 10)) // (32 * 10**9 * 10),
        ),
    ]
)
def test_compute_individual_penalty(genesis_state,
                                    config,
                                    slots_per_epoch,
                                    current_epoch,
                                    epochs_per_slashed_balances_vector,
                                    total_penalties,
                                    total_balance,
                                    expected_penalty):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
    )
    validator_index = 0
    penalty = _compute_individual_penalty(
        state=state,
        config=config,
        validator_index=validator_index,
        total_penalties=total_penalties,
        total_balance=total_balance,
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        'validator_count',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'epochs_per_slashed_balances_vector',
        'slashed_balances',
        'expected_penalty',
    ),
    [
        (
            10,
            4,
            8,
            8,
            8,
            (2 * 10**9, 10**9) + (0,) * 6,
            32 * 10**9 // 2**5,
        ),
    ]
)
def test_process_slashings(genesis_state,
                           config,
                           current_epoch,
                           slashed_balances,
                           slots_per_epoch,
                           epochs_per_slashed_balances_vector,
                           expected_penalty):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
        slashed_balances=slashed_balances,
    )
    slashing_validator_index = 0
    validator = state.validators[slashing_validator_index].copy(
        slashed=True,
        withdrawable_epoch=current_epoch + epochs_per_slashed_balances_vector // 2
    )
    state = state.update_validators(slashing_validator_index, validator)

    result_state = process_slashings(state, config)
    penalty = (
        state.balances[slashing_validator_index] -
        result_state.balances[slashing_validator_index]
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        'validator_count',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
    ),
    [
        (10, 4, 8, 8)
    ]
)
@pytest.mark.parametrize(
    (
        'min_validator_withdrawability_delay',
        'withdrawable_epoch',
        'exit_epoch',
        'is_eligible',
    ),
    [
        # current_epoch == validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        (4, FAR_FUTURE_EPOCH, 4, True),
        # withdrawable_epoch != FAR_FUTURE_EPOCH
        (4, 8, 4, False),
        # current_epoch < validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        (4, FAR_FUTURE_EPOCH, 5, False),
    ]
)
def test_process_exit_queue_eligible(genesis_state,
                                     config,
                                     current_epoch,
                                     min_validator_withdrawability_delay,
                                     withdrawable_epoch,
                                     exit_epoch,
                                     is_eligible):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
    )
    validator_index = 0

    # Set eligible validators
    state = state.update_validators(
        validator_index,
        state.validators[validator_index].copy(
            withdrawable_epoch=withdrawable_epoch,
            exit_epoch=exit_epoch,
        )
    )

    result_state = process_exit_queue(state, config)

    if is_eligible:
        # Check if they got prepared for withdrawal
        assert (
            result_state.validators[validator_index].withdrawable_epoch ==
            current_epoch + min_validator_withdrawability_delay
        )
    else:
        assert (
            result_state.validators[validator_index].withdrawable_epoch ==
            state.validators[validator_index].withdrawable_epoch
        )


@pytest.mark.parametrize(
    (
        'validator_count',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'min_validator_withdrawability_delay'
    ),
    [
        (10, 4, 4, 16, 4)
    ]
)
@pytest.mark.parametrize(
    (
        'max_exit_dequeues_per_epoch',
        'num_eligible_validators',
        'validator_exit_epochs',
    ),
    [
        # no  eligible validator
        (4, 0, ()),
        # max_exit_dequeues_per_epoch == num_eligible_validators
        (4, 4, (4, 5, 6, 7)),
        # max_exit_dequeues_per_epoch > num_eligible_validators
        (5, 4, (4, 5, 6, 7)),
        # max_exit_dequeues_per_epoch < num_eligible_validators
        (3, 4, (4, 5, 6, 7)),
        (3, 4, (7, 6, 5, 4)),
    ]
)
def test_process_exit_queue(genesis_state,
                            config,
                            current_epoch,
                            validator_count,
                            max_exit_dequeues_per_epoch,
                            min_validator_withdrawability_delay,
                            num_eligible_validators,
                            validator_exit_epochs):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
    )

    # Set eligible validators
    assert num_eligible_validators <= validator_count
    for i in range(num_eligible_validators):
        state = state.update_validators(
            i,
            state.validators[i].copy(
                exit_epoch=validator_exit_epochs[i],
            )
        )

    result_state = process_exit_queue(state, config)

    # Exit queue is sorted
    sorted_indices = sorted(
        range(num_eligible_validators),
        key=lambda i: validator_exit_epochs[i],
    )
    filtered_indices = sorted_indices[:min(max_exit_dequeues_per_epoch, num_eligible_validators)]

    for i in range(validator_count):
        if i in set(filtered_indices):
            # Check if they got prepared for withdrawal
            assert (
                result_state.validators[i].withdrawable_epoch ==
                current_epoch + min_validator_withdrawability_delay
            )
        else:
            assert (
                result_state.validators[i].withdrawable_epoch ==
                FAR_FUTURE_EPOCH
            )


#
# Final updates
#
@pytest.mark.parametrize(
    (
        'slots_per_epoch,'
        'epochs_per_historical_vector,'
        'state_slot,'
    ),
    [
        (4, 16, 4),
        (4, 16, 64),
    ]
)
def test_update_active_index_roots(genesis_state,
                                   committee_config,
                                   state_slot,
                                   slots_per_epoch,
                                   epochs_per_historical_vector,
                                   activation_exit_delay):
    state = genesis_state.copy(
        slot=state_slot,
    )

    result_state = _update_active_index_roots(state, committee_config)

    index_root = ssz.hash_tree_root(
        get_active_validator_indices(
            state.validators,
            slot_to_epoch(state.slot, slots_per_epoch),
        ),
        ssz.sedes.List(ssz.uint64),
    )

    target_epoch = state.next_epoch(slots_per_epoch) + activation_exit_delay
    assert result_state.active_index_roots[
        target_epoch % epochs_per_historical_vector
    ] == index_root


@pytest.mark.parametrize(
    (
        'validator_count,'
        'slots_per_epoch'
    ),
    [
        (10, 4),
    ]
)
def test_process_final_updates(genesis_state,
                               config,
                               sample_attestation_params):
    current_slot = 10
    state = genesis_state.copy(
        slot=current_slot,
    )
    current_index = state.next_epoch(
        config.SLOTS_PER_EPOCH
    ) % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    previous_index = state.current_epoch(
        config.SLOTS_PER_EPOCH
    ) % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR

    attestation = Attestation(**sample_attestation_params)
    previous_epoch_attestation_slot = current_slot - config.SLOTS_PER_EPOCH
    num_previous_epoch_attestations = 2
    previous_epoch_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=previous_epoch_attestation_slot
            )
        )
        for _ in range(num_previous_epoch_attestations)
    ]
    num_current_epoch_attestations = 3
    current_epoch_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=current_slot
            )
        )
        for _ in range(num_current_epoch_attestations)
    ]

    # Fill slashed_balances
    slashed_balance_of_previous_epoch = 100
    slashed_balances = update_tuple_item(
        state.slashed_balances,
        previous_index,
        slashed_balance_of_previous_epoch,
    )
    state = state.copy(
        slashed_balances=slashed_balances,
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )

    result_state = process_final_updates(state, config)

    assert (
        (
            result_state.slashed_balances[current_index] ==
            slashed_balance_of_previous_epoch
        ) and (
            result_state.randao_mixes[current_index] == get_randao_mix(
                state=state,
                epoch=state.current_epoch(config.SLOTS_PER_EPOCH),
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                epochs_per_historical_vector=config.EPOCHS_PER_HISTORICAL_VECTOR,
            )
        )
    )

    for attestation in result_state.previous_epoch_attestations:
        assert attestation.data.slot == current_slot
    assert len(result_state.current_epoch_attestations) == 0
