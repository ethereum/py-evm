import random

import pytest
import ssz

from eth2._utils.bitfield import get_empty_bitfield, set_voted
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_shard_delta,
    get_start_shard,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
    GWEI_PER_ETH,
    JUSTIFICATION_BITS_LENGTH,
)
from eth2.beacon.epoch_processing_helpers import get_base_reward
from eth2.beacon.helpers import (
    compute_epoch_of_slot,
    compute_start_slot_of_epoch,
    get_active_validator_indices,
    get_block_root,
    get_block_root_at_slot,
)
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _bft_threshold_met,
    _compute_next_active_index_roots,
    _determine_new_finalized_epoch,
    _determine_slashing_penalty,
    compute_activation_exit_epoch,
    get_attestation_deltas,
    get_crosslink_deltas,
    process_crosslinks,
    process_justification_and_finalization,
    process_registry_updates,
    process_slashings,
)
from eth2.beacon.tools.builder.validator import (
    get_crosslink_committees_at_slot,
    mk_all_pending_attestations_with_full_participation_in_epoch,
    mk_all_pending_attestations_with_some_participation_in_epoch,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import Gwei
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(
    "total_balance," "attesting_balance," "expected,",
    (
        (1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, True),
        (1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, False),
    ),
)
def test_bft_threshold_met(attesting_balance, total_balance, expected):
    assert _bft_threshold_met(attesting_balance, total_balance) == expected


@pytest.mark.parametrize(
    "justification_bits,"
    "previous_justified_epoch,"
    "current_justified_epoch,"
    "expected,",
    (
        # Rule 1
        ((False, True, True, True), 3, 3, 3),
        # Rule 2
        ((False, True, True, False), 4, 4, 4),
        # Rule 3
        ((True, True, True, False), 3, 4, 4),
        # Rule 4
        ((True, True, False, False), 2, 5, 5),
        # No finalize
        ((False, False, False, False), 2, 2, 1),
        ((True, True, True, True), 2, 2, 1),
    ),
)
def test_get_finalized_epoch(
    justification_bits, previous_justified_epoch, current_justified_epoch, expected
):
    current_epoch = 6
    finalized_epoch = 1
    assert (
        _determine_new_finalized_epoch(
            finalized_epoch,
            previous_justified_epoch,
            current_justified_epoch,
            current_epoch,
            justification_bits,
        )
        == expected
    )


def test_justification_without_mock(genesis_state, slots_per_historical_root, config):

    state = genesis_state
    state = process_justification_and_finalization(state, config)
    assert state.justification_bits == (False,) * JUSTIFICATION_BITS_LENGTH


def _convert_to_bitfield(bits):
    data = bits.to_bytes(1, "little")
    length = bits.bit_length()
    bitfield = get_empty_bitfield(length)
    for index in range(length):
        value = (data[index // 8] >> index % 8) % 2
        if value:
            bitfield = set_voted(bitfield, index)
    return (bitfield + (False,) * (4 - length))[0:4]


@pytest.mark.parametrize(
    (
        "current_epoch",
        "current_epoch_justifiable",
        "previous_epoch_justifiable",
        "previous_justified_epoch",
        "current_justified_epoch",
        "justification_bits",
        "finalized_epoch",
        "justified_epoch_after",
        "justification_bits_after",
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
def test_process_justification_and_finalization(
    genesis_state,
    current_epoch,
    current_epoch_justifiable,
    previous_epoch_justifiable,
    previous_justified_epoch,
    current_justified_epoch,
    justification_bits,
    finalized_epoch,
    justified_epoch_after,
    justification_bits_after,
    finalized_epoch_after,
    config,
):
    justification_bits = _convert_to_bitfield(justification_bits)
    justification_bits_after = _convert_to_bitfield(justification_bits_after)
    previous_epoch = max(current_epoch - 1, 0)
    slot = (current_epoch + 1) * config.SLOTS_PER_EPOCH - 1

    state = genesis_state.copy(
        slot=slot,
        previous_justified_checkpoint=Checkpoint(epoch=previous_justified_epoch),
        current_justified_checkpoint=Checkpoint(epoch=current_justified_epoch),
        justification_bits=justification_bits,
        finalized_checkpoint=Checkpoint(epoch=finalized_epoch),
        block_roots=tuple(
            i.to_bytes(32, "little") for i in range(config.SLOTS_PER_HISTORICAL_ROOT)
        ),
    )

    if previous_epoch_justifiable:
        attestations = mk_all_pending_attestations_with_full_participation_in_epoch(
            state, previous_epoch, config
        )
        state = state.copy(previous_epoch_attestations=attestations)

    if current_epoch_justifiable:
        attestations = mk_all_pending_attestations_with_full_participation_in_epoch(
            state, current_epoch, config
        )
        state = state.copy(current_epoch_attestations=attestations)

    post_state = process_justification_and_finalization(state, config)

    assert (
        post_state.previous_justified_checkpoint.epoch
        == state.current_justified_checkpoint.epoch
    )
    assert post_state.current_justified_checkpoint.epoch == justified_epoch_after
    assert post_state.justification_bits == justification_bits_after
    assert post_state.finalized_checkpoint.epoch == finalized_epoch_after


@pytest.mark.parametrize(("slots_per_epoch," "shard_count,"), [(10, 10)])
@pytest.mark.parametrize(
    ("success_in_previous_epoch," "success_in_current_epoch,"),
    [(False, False), (True, False), (False, True)],
)
def test_process_crosslinks(
    genesis_state, config, success_in_previous_epoch, success_in_current_epoch
):
    shard_count = config.SHARD_COUNT
    current_slot = config.SLOTS_PER_EPOCH * 5 - 1
    current_epoch = compute_epoch_of_slot(current_slot, config.SLOTS_PER_EPOCH)
    assert current_epoch - 4 >= 0

    previous_crosslinks = tuple(
        Crosslink(shard=i, start_epoch=current_epoch - 4, end_epoch=current_epoch - 3)
        for i in range(shard_count)
    )
    parent_crosslinks = tuple(
        Crosslink(
            shard=i,
            parent_root=previous_crosslinks[i].hash_tree_root,
            start_epoch=current_epoch - 2,
            end_epoch=current_epoch - 1,
        )
        for i in range(shard_count)
    )
    new_crosslinks = tuple(
        Crosslink(
            shard=i,
            parent_root=parent_crosslinks[i].hash_tree_root,
            start_epoch=current_epoch - 1,
            end_epoch=current_epoch,
        )
        for i in range(shard_count)
    )

    # generate expected state for correct crosslink generation
    state = genesis_state.copy(
        slot=current_slot,
        previous_crosslinks=previous_crosslinks,
        current_crosslinks=parent_crosslinks,
    )

    previous_epoch = current_epoch - 1

    expected_success_shards = set()
    previous_epoch_attestations = tuple(
        mk_all_pending_attestations_with_some_participation_in_epoch(
            state, previous_epoch, config, 0.7 if success_in_previous_epoch else 0
        )
    )
    if success_in_previous_epoch:
        for a in previous_epoch_attestations:
            expected_success_shards.add(a.data.crosslink.shard)

    current_epoch_attestations = tuple(
        mk_all_pending_attestations_with_some_participation_in_epoch(
            state, current_epoch, config, 0.7 if success_in_current_epoch else 0
        )
    )
    if success_in_current_epoch:
        for a in current_epoch_attestations:
            expected_success_shards.add(a.data.crosslink.shard)

    state = state.copy(
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )

    post_state = process_crosslinks(state, config)

    assert post_state.previous_crosslinks == state.current_crosslinks

    for shard in range(shard_count):
        crosslink = post_state.current_crosslinks[shard]
        if shard in expected_success_shards:
            if success_in_current_epoch:
                expected_crosslink = new_crosslinks[shard]
            else:
                expected_crosslink = parent_crosslinks[shard]
            assert crosslink == expected_crosslink
        else:
            # no change
            assert crosslink == state.current_crosslinks[shard]


# TODO better testing on attestation deltas
@pytest.mark.parametrize(("validator_count,"), [(10)])
@pytest.mark.parametrize(
    ("finalized_epoch", "current_slot"),
    [(4, 384), (3, 512)],  # epochs_since_finality <= 4  # epochs_since_finality > 4
)
def test_get_attestation_deltas(
    genesis_state,
    config,
    slots_per_epoch,
    target_committee_size,
    shard_count,
    min_attestation_inclusion_delay,
    inactivity_penalty_quotient,
    finalized_epoch,
    current_slot,
    sample_pending_attestation_record_params,
    sample_attestation_data_params,
):
    state = genesis_state.copy(
        slot=current_slot, finalized_checkpoint=Checkpoint(epoch=finalized_epoch)
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    epoch_start_shard = get_start_shard(state, previous_epoch, CommitteeConfig(config))
    shard_delta = get_shard_delta(state, previous_epoch, CommitteeConfig(config))

    a = epoch_start_shard
    b = epoch_start_shard + shard_delta
    if a > b:
        valid_shards_for_epoch = range(b, a)
    else:
        valid_shards_for_epoch = range(a, b)

    indices_to_check = set()

    prev_epoch_start_slot = compute_start_slot_of_epoch(previous_epoch, slots_per_epoch)
    prev_epoch_attestations = tuple()
    for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch):
        committee, shard = get_crosslink_committees_at_slot(
            state, slot, CommitteeConfig(config)
        )[0]
        if not committee:
            continue
        if shard not in valid_shards_for_epoch:
            continue
        participants_bitfield = get_empty_bitfield(len(committee))
        for i, index in enumerate(committee):
            indices_to_check.add(index)
            participants_bitfield = set_voted(participants_bitfield, i)
        prev_epoch_attestations += (
            PendingAttestation(**sample_pending_attestation_record_params).copy(
                aggregation_bits=participants_bitfield,
                inclusion_delay=min_attestation_inclusion_delay,
                proposer_index=get_beacon_proposer_index(
                    state.copy(slot=slot), CommitteeConfig(config)
                ),
                data=AttestationData(**sample_attestation_data_params).copy(
                    crosslink=Crosslink(shard=shard),
                    target=Checkpoint(
                        epoch=previous_epoch,
                        root=get_block_root(
                            state,
                            previous_epoch,
                            config.SLOTS_PER_EPOCH,
                            config.SLOTS_PER_HISTORICAL_ROOT,
                        ),
                    ),
                    beacon_block_root=get_block_root_at_slot(
                        state, slot, config.SLOTS_PER_HISTORICAL_ROOT
                    ),
                ),
            ),
        )
    state = state.copy(previous_epoch_attestations=prev_epoch_attestations)

    rewards_received, penalties_received = get_attestation_deltas(state, config)

    # everyone attested, no penalties
    assert sum(penalties_received) == 0
    the_reward = rewards_received[0]
    # everyone performed the same, equal rewards
    assert sum(rewards_received) // len(rewards_received) == the_reward


@pytest.mark.parametrize(
    (
        "validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "current_slot,"
        "num_attesting_validators,"
        "genesis_slot,"
    ),
    [(50, 10, 5, 10, 100, 3, 0), (50, 10, 5, 10, 100, 4, 0)],
)
def test_process_rewards_and_penalties_for_crosslinks(
    genesis_state,
    config,
    slots_per_epoch,
    target_committee_size,
    shard_count,
    current_slot,
    num_attesting_validators,
    max_effective_balance,
    min_attestation_inclusion_delay,
    sample_attestation_data_params,
    sample_pending_attestation_record_params,
):
    state = genesis_state.copy(slot=current_slot)
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)

    prev_epoch_start_slot = compute_start_slot_of_epoch(previous_epoch, slots_per_epoch)
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(state, slot, CommitteeConfig(config))[0]
        for slot in range(
            prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch
        )
    ]

    # Record which validators attest during each slot for reward collation.
    each_slot_attestion_validators_list = []

    epoch_start_shard = get_start_shard(state, previous_epoch, CommitteeConfig(config))
    shard_delta = get_shard_delta(state, previous_epoch, CommitteeConfig(config))

    a = epoch_start_shard
    b = epoch_start_shard + shard_delta
    if a > b:
        valid_shards_for_epoch = range(b, a)
    else:
        valid_shards_for_epoch = range(a, b)

    indices_to_check = set()

    previous_epoch_attestations = []
    for committee, shard in prev_epoch_crosslink_committees:
        if shard not in valid_shards_for_epoch:
            continue
        for index in committee:
            indices_to_check.add(index)
        # Randomly sample `num_attesting_validators` validators
        # from the committee to attest in this slot.
        crosslink_attesting_validators = random.sample(
            committee, num_attesting_validators
        )
        each_slot_attestion_validators_list.append(crosslink_attesting_validators)
        participants_bitfield = get_empty_bitfield(len(committee))
        for index in crosslink_attesting_validators:
            participants_bitfield = set_voted(
                participants_bitfield, committee.index(index)
            )
        previous_epoch_attestations.append(
            PendingAttestation(**sample_pending_attestation_record_params).copy(
                aggregation_bits=participants_bitfield,
                data=AttestationData(**sample_attestation_data_params).copy(
                    target=Checkpoint(epoch=previous_epoch),
                    crosslink=Crosslink(
                        shard=shard, parent_root=Crosslink().hash_tree_root
                    ),
                ),
            )
        )
    state = state.copy(previous_epoch_attestations=tuple(previous_epoch_attestations))

    rewards_received, penalties_received = get_crosslink_deltas(state, config)

    expected_rewards_received = {index: 0 for index in range(len(state.validators))}
    validator_balance = max_effective_balance
    for i in range(slots_per_epoch):
        crosslink_committee, shard = prev_epoch_crosslink_committees[i]
        if shard not in valid_shards_for_epoch:
            continue
        attesting_validators = each_slot_attestion_validators_list[i]
        total_attesting_balance = len(attesting_validators) * validator_balance
        total_committee_balance = len(crosslink_committee) * validator_balance
        for index in crosslink_committee:
            if index in attesting_validators:
                reward = (
                    get_base_reward(state=state, index=index, config=config)
                    * total_attesting_balance
                    // total_committee_balance
                )
                expected_rewards_received[index] += reward
            else:
                penalty = get_base_reward(state=state, index=index, config=config)
                expected_rewards_received[index] -= penalty

    # Check the rewards/penalties match
    for index in range(len(state.validators)):
        if index not in indices_to_check:
            continue
        assert (
            rewards_received[index] - penalties_received[index]
            == expected_rewards_received[index]
        )


@pytest.mark.parametrize(
    ("validator_count", "slots_per_epoch", "target_committee_size", "shard_count"),
    [(10, 10, 9, 10)],
)
def test_process_registry_updates(
    validator_count, genesis_state, config, slots_per_epoch
):
    activation_index = len(genesis_state.validators)
    exiting_index = len(genesis_state.validators) - 1

    activating_validator = Validator.create_pending_validator(
        pubkey=b"\x10" * 48,
        withdrawal_credentials=b"\x11" * 32,
        amount=Gwei(32 * GWEI_PER_ETH),
        config=config,
    )

    state = genesis_state.copy(
        validators=genesis_state.validators[:exiting_index]
        + (
            genesis_state.validators[exiting_index].copy(
                effective_balance=config.EJECTION_BALANCE - 1
            ),
        )
        + (activating_validator,),
        balances=genesis_state.balances + (config.MAX_EFFECTIVE_BALANCE,),
    )

    # handles activations
    post_state = process_registry_updates(state, config)

    # Check if the activating_validator is activated
    pre_activation_validator = state.validators[activation_index]
    post_activation_validator = post_state.validators[activation_index]
    assert pre_activation_validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
    assert pre_activation_validator.activation_epoch == FAR_FUTURE_EPOCH
    assert post_activation_validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH
    activation_epoch = compute_activation_exit_epoch(
        state.current_epoch(config.SLOTS_PER_EPOCH), config.ACTIVATION_EXIT_DELAY
    )
    assert post_activation_validator.is_active(activation_epoch)
    # Check if the activating_validator is exited
    pre_exiting_validator = state.validators[exiting_index]
    post_exiting_validator = post_state.validators[exiting_index]
    assert pre_exiting_validator.exit_epoch == FAR_FUTURE_EPOCH
    assert pre_exiting_validator.withdrawable_epoch == FAR_FUTURE_EPOCH
    assert state.validators[exiting_index].effective_balance <= config.EJECTION_BALANCE
    assert post_exiting_validator.exit_epoch != FAR_FUTURE_EPOCH
    assert post_exiting_validator.withdrawable_epoch != FAR_FUTURE_EPOCH
    assert post_exiting_validator.withdrawable_epoch > post_exiting_validator.exit_epoch


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "genesis_slot",
        "current_epoch",
        "epochs_per_slashings_vector",
    ),
    [(10, 4, 8, 8, 8)],
)
@pytest.mark.parametrize(
    ("total_penalties", "total_balance", "expected_penalty"),
    [
        # total_penalties * 3 is less than total_balance
        (
            32 * 10 ** 9,  # 1 ETH
            (32 * 10 ** 9 * 10),
            # effective_balance * total_penalties * 3 // total_balance
            ((32 * 10 ** 9) // 10 ** 9)
            * (3 * 32 * 10 ** 9)
            // (32 * 10 ** 9 * 10)
            * 10 ** 9,
        ),
        # total_balance is less than total_penalties * 3
        (
            32 * 4 * 10 ** 9,
            (32 * 10 ** 9 * 10),
            # effective_balance * total_balance // total_balance,
            (32 * 10 ** 9)
            // 10 ** 9
            * (32 * 10 ** 9 * 10)
            // (32 * 10 ** 9 * 10)
            * 10 ** 9,
        ),
    ],
)
def test_determine_slashing_penalty(
    genesis_state,
    config,
    slots_per_epoch,
    current_epoch,
    epochs_per_slashings_vector,
    total_penalties,
    total_balance,
    expected_penalty,
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(current_epoch, slots_per_epoch)
    )
    # if the size of the v-set changes then update the parameters above
    assert len(state.validators) == 10
    validator_index = 0
    penalty = _determine_slashing_penalty(
        total_penalties,
        total_balance,
        state.validators[validator_index].effective_balance,
        config.EFFECTIVE_BALANCE_INCREMENT,
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "current_epoch",
        "epochs_per_slashings_vector",
        "slashings",
        "expected_penalty",
    ),
    [
        (
            10,
            4,
            8,
            8,
            (19 * 10 ** 9, 10 ** 9) + (0,) * 6,
            (32 * 10 ** 9 // 10 ** 9 * 60 * 10 ** 9) // (320 * 10 ** 9) * 10 ** 9,
        )
    ],
)
def test_process_slashings(
    genesis_state,
    config,
    current_epoch,
    slashings,
    slots_per_epoch,
    epochs_per_slashings_vector,
    expected_penalty,
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(current_epoch, slots_per_epoch),
        slashings=slashings,
    )
    slashing_validator_index = 0
    validator = state.validators[slashing_validator_index].copy(
        slashed=True,
        withdrawable_epoch=current_epoch + epochs_per_slashings_vector // 2,
    )
    state = state.update_validator(slashing_validator_index, validator)

    result_state = process_slashings(state, config)
    penalty = (
        state.balances[slashing_validator_index]
        - result_state.balances[slashing_validator_index]
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    ("slots_per_epoch," "epochs_per_historical_vector," "state_slot,"),
    [(4, 16, 4), (4, 16, 64)],
)
def test_update_active_index_roots(
    genesis_state,
    config,
    state_slot,
    slots_per_epoch,
    epochs_per_historical_vector,
    activation_exit_delay,
):
    state = genesis_state.copy(slot=state_slot)

    result = _compute_next_active_index_roots(state, config)

    index_root = ssz.get_hash_tree_root(
        get_active_validator_indices(
            state.validators, compute_epoch_of_slot(state.slot, slots_per_epoch)
        ),
        ssz.sedes.List(ssz.uint64, config.VALIDATOR_REGISTRY_LIMIT),
    )

    target_epoch = state.next_epoch(slots_per_epoch) + activation_exit_delay
    assert result[target_epoch % epochs_per_historical_vector] == index_root
