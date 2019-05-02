from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Sequence,
    Tuple,
)

from eth_utils import (
    to_dict,
)
from eth_utils.toolz import (
    curry,
    first,
)
import ssz

from eth2.beacon import helpers
from eth2._utils.numeric import (
    is_power_of_two,
)
from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.committee_helpers import (
    get_attester_indices_from_attestations,
    get_beacon_proposer_index,
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
    slot_to_epoch,
)
from eth2.beacon.epoch_processing_helpers import (
    get_base_reward,
    get_epoch_boundary_attesting_balance,
    get_inactivity_penalty,
    get_inclusion_infos,
    get_previous_epoch_boundary_attestations,
    get_previous_epoch_matching_head_attestations,
    get_total_balance,
    get_total_balance_from_effective_balances,
    get_winning_root_and_participants,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_effective_balance,
    get_epoch_start_slot,
    get_randao_mix,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
    exit_validator,
    prepare_validator_for_withdrawal,
)
from eth2.beacon.datastructures.inclusion_info import InclusionInfo
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.eth1_data_vote import Eth1DataVote
from eth2.beacon.types.historical_batch import HistoricalBatch
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Slot,
    ValidatorIndex,
)


#
# Eth1 data votes
#
def _majority_threshold(config: Eth2Config) -> int:
    """
    Return the value constituting the majority threshold for an Eth1 data vote.
    """
    return config.EPOCHS_PER_ETH1_VOTING_PERIOD * config.SLOTS_PER_EPOCH


@curry
def _is_majority_vote(config: Eth2Config, vote: Eth1DataVote) -> bool:
    return vote.vote_count * 2 > _majority_threshold(config)


def _update_eth1_vote_if_exists(state: BeaconState, config: Eth2Config) -> BeaconState:
    """
    This function searches the 'pending' Eth1 data votes in ``state`` to find one Eth1 data vote
    containing majority support.

    If such a vote is found, update the ``state`` entry for the latest vote.
    Regardless of the existence of such a vote, clear the 'pending' storage.
    """

    latest_eth1_data = state.latest_eth1_data

    try:
        majority_vote = first(
            filter(_is_majority_vote(config), state.eth1_data_votes)
        )
        latest_eth1_data = majority_vote.eth1_data
    except StopIteration:
        pass

    return state.copy(
        latest_eth1_data=latest_eth1_data,
        eth1_data_votes=(),
    )


def process_eth1_data_votes(state: BeaconState, config: Eth2Config) -> BeaconState:
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    should_process = next_epoch % config.EPOCHS_PER_ETH1_VOTING_PERIOD == 0
    if should_process:
        return _update_eth1_vote_if_exists(state, config)
    return state


#
# Justification
#

def _is_epoch_justifiable(state: BeaconState,
                          attestations: Sequence[PendingAttestation],
                          epoch: Epoch,
                          config: Eth2Config) -> bool:
    """
    Determine if epoch boundary attesting balance is greater than 2/3 of total_balance
    for the given ``epoch``.
    """
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        epoch,
    )

    if not active_validator_indices:
        return False

    total_balance = get_total_balance(
        state.validator_balances,
        active_validator_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )

    attesting_balance = get_epoch_boundary_attesting_balance(state, attestations, epoch, config)

    return 3 * attesting_balance >= 2 * total_balance


def _get_finalized_epoch(
        justification_bitfield: int,
        previous_justified_epoch: Epoch,
        current_justified_epoch: Epoch,
        finalized_epoch: Epoch,
        previous_epoch: Epoch) -> Tuple[Epoch, int]:

    rule_1 = (
        (justification_bitfield >> 1) % 8 == 0b111 and
        previous_justified_epoch == previous_epoch - 2
    )
    rule_2 = (
        (justification_bitfield >> 1) % 4 == 0b11 and
        previous_justified_epoch == previous_epoch - 1
    )
    rule_3 = (
        justification_bitfield % 8 == 0b111 and
        current_justified_epoch == previous_epoch - 1
    )
    rule_4 = (
        justification_bitfield % 4 == 0b11 and
        current_justified_epoch == previous_epoch
    )
    # Check the rule in the order that can finalize higher epoch possible
    # The second output indicating what rule triggered is for testing purpose
    if rule_4:
        return current_justified_epoch, 4
    elif rule_3:
        return current_justified_epoch, 3
    elif rule_2:
        return previous_justified_epoch, 2
    elif rule_1:
        return previous_justified_epoch, 1
    else:
        return finalized_epoch, 0


def process_justification(state: BeaconState, config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH)

    current_epoch_justifiable = _is_epoch_justifiable(
        state,
        state.current_epoch_attestations,
        current_epoch,
        config,
    )
    previous_epoch_justifiable = _is_epoch_justifiable(
        state,
        state.previous_epoch_attestations,
        previous_epoch,
        config,
    )

    _justification_bitfield = state.justification_bitfield << 1
    if previous_epoch_justifiable and current_epoch_justifiable:
        justification_bitfield = _justification_bitfield | 3
    elif previous_epoch_justifiable:
        justification_bitfield = _justification_bitfield | 2
    elif current_epoch_justifiable:
        justification_bitfield = _justification_bitfield | 1
    else:
        justification_bitfield = _justification_bitfield

    if current_epoch_justifiable:
        new_justified_epoch = current_epoch
    elif previous_epoch_justifiable:
        new_justified_epoch = previous_epoch
    else:
        new_justified_epoch = state.current_justified_epoch

    new_finalized_epoch, _ = _get_finalized_epoch(
        justification_bitfield,
        state.previous_justified_epoch,
        state.current_justified_epoch,
        state.finalized_epoch,
        previous_epoch,
    )

    # Update state
    state = state.copy(
        previous_justified_epoch=state.current_justified_epoch,
        previous_justified_root=state.current_justified_root,
        justification_bitfield=justification_bitfield,
    )

    if new_justified_epoch != state.current_justified_epoch:
        state = state.copy(
            current_justified_epoch=new_justified_epoch,
            current_justified_root=get_block_root(
                state,
                get_epoch_start_slot(new_justified_epoch, config.SLOTS_PER_EPOCH),
                config.SLOTS_PER_HISTORICAL_ROOT,
            ),
        )

    if new_finalized_epoch != state.finalized_epoch:
        state = state.copy(
            finalized_epoch=new_finalized_epoch,
            finalized_root=get_block_root(
                state,
                get_epoch_start_slot(new_finalized_epoch, config.SLOTS_PER_EPOCH),
                config.SLOTS_PER_HISTORICAL_ROOT,
            )
        )

    return state


#
# Crosslinks
#
def process_crosslinks(state: BeaconState, config: Eth2Config) -> BeaconState:
    """
    Implement 'per-epoch-processing.crosslinks' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#crosslinks

    For each shard from the past two epochs, find the shard block
    root that has been attested to by the most stake.
    If enough(>= 2/3 total stake) attesting stake, update the crosslink record of that shard.
    Return resulting ``state``
    """
    latest_crosslinks = state.latest_crosslinks
    effective_balances = {
        ValidatorIndex(index): get_effective_balance(
            state.validator_balances,
            ValidatorIndex(index),
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in range(len(state.validator_registry))
    }
    previous_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    next_epoch_start_slot = get_epoch_start_slot(
        state.next_epoch(config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    for slot in range(previous_epoch_start_slot, next_epoch_start_slot):
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )
        for crosslink_committee, shard in crosslink_committees_at_slot:
            winning_root, attesting_validator_indices = get_winning_root_and_participants(
                state=state,
                shard=shard,
                effective_balances=effective_balances,
                committee_config=CommitteeConfig(config),
            )
            if len(attesting_validator_indices) > 0:
                total_attesting_balance = get_total_balance(
                    state.validator_balances,
                    attesting_validator_indices,
                    config.MAX_DEPOSIT_AMOUNT,
                )
                total_balance = get_total_balance(
                    state.validator_balances,
                    crosslink_committee,
                    config.MAX_DEPOSIT_AMOUNT,
                )
                if 3 * total_attesting_balance >= 2 * total_balance:
                    latest_crosslinks = update_tuple_item(
                        latest_crosslinks,
                        shard,
                        Crosslink(
                            epoch=slot_to_epoch(Slot(slot), config.SLOTS_PER_EPOCH),
                            crosslink_data_root=winning_root,
                        ),
                    )
    state = state.copy(
        latest_crosslinks=latest_crosslinks,
    )
    return state


@to_dict
def _update_rewards_or_penalies(
        index: ValidatorIndex,
        amount: Gwei,
        rewards_or_penalties: Dict[ValidatorIndex, Gwei]) -> Iterable[Tuple[ValidatorIndex, Gwei]]:
    for i in rewards_or_penalties:
        if i == index:
            yield i, Gwei(rewards_or_penalties[i] + amount)
        else:
            yield i, rewards_or_penalties[i]


def _compute_normal_justification_and_finalization_deltas(
        state: BeaconState,
        config: Eth2Config,
        previous_epoch_active_validator_indices: Sequence[ValidatorIndex],
        previous_total_balance: Gwei,
        previous_epoch_attester_indices: Sequence[ValidatorIndex],
        previous_epoch_boundary_attester_indices: Sequence[ValidatorIndex],
        previous_epoch_head_attester_indices: Sequence[ValidatorIndex],
        inclusion_infos: Dict[ValidatorIndex, InclusionInfo],
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei]) -> Tuple[Dict[ValidatorIndex, Gwei], Dict[ValidatorIndex, Gwei]]:  # noqa: E501
    rewards_received = {
        ValidatorIndex(index): Gwei(0)
        for index in range(len(state.validator_registry))
    }
    penalties_received = rewards_received.copy()
    previous_epoch_attesting_balance = get_total_balance_from_effective_balances(
        effective_balances,
        previous_epoch_attester_indices,
    )
    previous_epoch_boundary_attesting_balance = get_total_balance_from_effective_balances(
        effective_balances,
        previous_epoch_boundary_attester_indices,
    )
    previous_epoch_head_attesting_balance = get_total_balance_from_effective_balances(
        effective_balances,
        previous_epoch_head_attester_indices,
    )
    for index in previous_epoch_active_validator_indices:
        # Expected FFG source
        if index in previous_epoch_attester_indices:
            rewards_received = _update_rewards_or_penalies(
                index,
                base_rewards[index] * previous_epoch_attesting_balance // previous_total_balance,
                rewards_received,
            )
            # Inclusion speed bonus
            rewards_received = _update_rewards_or_penalies(
                index,
                (
                    base_rewards[index] * config.MIN_ATTESTATION_INCLUSION_DELAY //
                    inclusion_infos[index].inclusion_distance
                ),
                rewards_received,
            )
        else:
            penalties_received = _update_rewards_or_penalies(
                index,
                base_rewards[index],
                penalties_received,
            )
        # Expected FFG target
        if index in previous_epoch_boundary_attester_indices:
            rewards_received = _update_rewards_or_penalies(
                index,
                (
                    base_rewards[index] * previous_epoch_boundary_attesting_balance //
                    previous_total_balance
                ),
                rewards_received,
            )
        else:
            penalties_received = _update_rewards_or_penalies(
                index,
                base_rewards[index],
                penalties_received,
            )
        # Expected head
        if index in previous_epoch_head_attester_indices:
            rewards_received = _update_rewards_or_penalies(
                index,
                (
                    base_rewards[index] * previous_epoch_head_attesting_balance //
                    previous_total_balance
                ),
                rewards_received,
            )
        else:
            penalties_received = _update_rewards_or_penalies(
                index,
                base_rewards[index],
                penalties_received,
            )
        # Proposer bonus
        if index in previous_epoch_attester_indices:
            proposer_index = get_beacon_proposer_index(
                state,
                inclusion_infos[index].inclusion_slot,
                CommitteeConfig(config),
            )
            rewards_received = _update_rewards_or_penalies(
                proposer_index,
                base_rewards[index] // config.ATTESTATION_INCLUSION_REWARD_QUOTIENT,
                rewards_received,
            )
    return (rewards_received, penalties_received)


def _compute_inactivity_leak_deltas(
        state: BeaconState,
        config: Eth2Config,
        previous_epoch_active_validator_indices: Sequence[ValidatorIndex],
        previous_epoch_attester_indices: Sequence[ValidatorIndex],
        previous_epoch_boundary_attester_indices: Sequence[ValidatorIndex],
        previous_epoch_head_attester_indices: Sequence[ValidatorIndex],
        inclusion_infos: Dict[ValidatorIndex, InclusionInfo],
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei],
        epochs_since_finality: int) -> Tuple[Dict[ValidatorIndex, Gwei], Dict[ValidatorIndex, Gwei]]:  # noqa: E501
    inactivity_penalties = {
        ValidatorIndex(index): get_inactivity_penalty(
            base_reward=base_rewards[ValidatorIndex(index)],
            effective_balance=effective_balances[ValidatorIndex(index)],
            epochs_since_finality=epochs_since_finality,
            inactivity_penalty_quotient=config.INACTIVITY_PENALTY_QUOTIENT,
        )
        for index in range(len(state.validator_registry))
    }
    rewards_received = {
        ValidatorIndex(index): Gwei(0)
        for index in range(len(state.validator_registry))
    }
    penalties_received = rewards_received.copy()
    for index in previous_epoch_active_validator_indices:
        if index not in previous_epoch_attester_indices:
            penalties_received = _update_rewards_or_penalies(
                index,
                inactivity_penalties[index],
                penalties_received,
            )
        else:
            # If a validator did attest, apply a small penalty
            # for getting attestations included late
            rewards_received = _update_rewards_or_penalies(
                index,
                (
                    base_rewards[index] * config.MIN_ATTESTATION_INCLUSION_DELAY //
                    inclusion_infos[index].inclusion_distance
                ),
                rewards_received,
            )
            penalties_received = _update_rewards_or_penalies(
                index,
                base_rewards[index],
                penalties_received,
            )
        if index not in previous_epoch_boundary_attester_indices:
            penalties_received = _update_rewards_or_penalies(
                index,
                inactivity_penalties[index],
                penalties_received,
            )
        if index not in previous_epoch_head_attester_indices:
            penalties_received = _update_rewards_or_penalies(
                index,
                base_rewards[index],
                penalties_received,
            )

    # Penalize slashed-but-inactive validators as though they were active but offline
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    for i in range(len(state.validator_registry)):
        eligible = (
            i not in previous_epoch_active_validator_indices and
            state.validator_registry[ValidatorIndex(i)].slashed and
            current_epoch < state.validator_registry[i].withdrawable_epoch
        )
        if eligible:
            penalties_received = _update_rewards_or_penalies(
                ValidatorIndex(i),
                2 * inactivity_penalties[ValidatorIndex(i)] + base_rewards[ValidatorIndex(i)],
                penalties_received,
            )
    return (rewards_received, penalties_received)


@curry
def _process_rewards_and_penalties_for_finality(
        state: BeaconState,
        config: Eth2Config,
        previous_epoch_active_validator_indices: Sequence[ValidatorIndex],
        previous_total_balance: Gwei,
        previous_epoch_attestations: Sequence[Attestation],
        previous_epoch_attester_indices: Sequence[ValidatorIndex],
        inclusion_infos: Dict[ValidatorIndex, InclusionInfo],
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei]) -> Tuple[Dict[ValidatorIndex, Gwei], Dict[ValidatorIndex, Gwei]]:  # noqa: E501
    previous_epoch_boundary_attestations = get_previous_epoch_boundary_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    previous_epoch_boundary_attester_indices = get_attester_indices_from_attestations(
        state=state,
        attestations=previous_epoch_boundary_attestations,
        committee_config=CommitteeConfig(config),
    )

    previous_epoch_head_attestations = get_previous_epoch_matching_head_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    previous_epoch_head_attester_indices = get_attester_indices_from_attestations(
        state=state,
        attestations=previous_epoch_head_attestations,
        committee_config=CommitteeConfig(config),
    )

    epochs_since_finality = state.next_epoch(config.SLOTS_PER_EPOCH) - state.finalized_epoch
    if epochs_since_finality <= 4:
        return _compute_normal_justification_and_finalization_deltas(
            state,
            config,
            previous_epoch_active_validator_indices,
            previous_total_balance,
            previous_epoch_attester_indices,
            previous_epoch_boundary_attester_indices,
            previous_epoch_head_attester_indices,
            inclusion_infos,
            effective_balances,
            base_rewards,
        )

    # epochs_since_finality > 4
    else:
        return _compute_inactivity_leak_deltas(
            state,
            config,
            previous_epoch_active_validator_indices,
            previous_epoch_attester_indices,
            previous_epoch_boundary_attester_indices,
            previous_epoch_head_attester_indices,
            inclusion_infos,
            effective_balances,
            base_rewards,
            epochs_since_finality,
        )


@curry
def _process_rewards_and_penalties_for_crosslinks(
        state: BeaconState,
        config: Eth2Config,
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei]) -> Tuple[Dict[ValidatorIndex, Gwei], Dict[ValidatorIndex, Gwei]]:  # noqa: E501
    previous_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    current_epoch_start_slot = get_epoch_start_slot(
        state.current_epoch(config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    rewards_received = {
        ValidatorIndex(index): Gwei(0)
        for index in range(len(state.validator_registry))
    }
    penalties_received = rewards_received.copy()
    for slot in range(previous_epoch_start_slot, current_epoch_start_slot):
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )
        for crosslink_committee, shard in crosslink_committees_at_slot:
            winning_root, attesting_validator_indices = get_winning_root_and_participants(
                state=state,
                shard=shard,
                effective_balances=effective_balances,
                committee_config=CommitteeConfig(config),
            )
            total_attesting_balance = get_total_balance(
                state.validator_balances,
                attesting_validator_indices,
                config.MAX_DEPOSIT_AMOUNT,
            )
            total_balance = get_total_balance_from_effective_balances(
                effective_balances,
                crosslink_committee,
            )
            for index in attesting_validator_indices:
                rewards_received = _update_rewards_or_penalies(
                    index,
                    base_rewards[index] * total_attesting_balance // total_balance,
                    rewards_received,
                )
            for index in set(crosslink_committee).difference(attesting_validator_indices):
                penalties_received = _update_rewards_or_penalies(
                    index,
                    base_rewards[index],
                    penalties_received,
                )
    return (rewards_received, penalties_received)


def process_rewards_and_penalties(state: BeaconState, config: Eth2Config) -> BeaconState:
    # Compute previous epoch active validator indices and the total balance they account for
    # for later use.
    previous_epoch_active_validator_indices = set(
        get_active_validator_indices(
            state.validator_registry,
            state.previous_epoch(config.SLOTS_PER_EPOCH)
        )
    )
    previous_total_balance: Gwei = get_total_balance(
        state.validator_balances,
        tuple(previous_epoch_active_validator_indices),
        config.MAX_DEPOSIT_AMOUNT,
    )

    # Compute previous epoch attester indices and the total balance they account for
    # for later use.
    previous_epoch_attestations = state.previous_epoch_attestations
    previous_epoch_attester_indices = get_attester_indices_from_attestations(
        state=state,
        attestations=previous_epoch_attestations,
        committee_config=CommitteeConfig(config),
    )

    # Compute inclusion slot/distance of previous attestations for later use.
    inclusion_infos = get_inclusion_infos(
        state=state,
        attestations=previous_epoch_attestations,
        committee_config=CommitteeConfig(config),
    )

    # Compute effective balance of each previous epoch active validator for later use
    effective_balances = {
        ValidatorIndex(index): get_effective_balance(
            state.validator_balances,
            ValidatorIndex(index),
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in range(len(state.validator_registry))
    }
    # Compute base reward of each previous epoch active validator for later use
    base_rewards = {
        ValidatorIndex(index): get_base_reward(
            state=state,
            index=ValidatorIndex(index),
            base_reward_quotient=config.BASE_REWARD_QUOTIENT,
            previous_total_balance=previous_total_balance,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
        )
        for index in range(len(state.validator_registry))
    }

    # 1. Process rewards and penalties for justification and finalization
    finality_rewards, finality_penalties = _process_rewards_and_penalties_for_finality(
        state,
        config,
        previous_epoch_active_validator_indices,
        previous_total_balance,
        previous_epoch_attestations,
        previous_epoch_attester_indices,
        inclusion_infos,
        effective_balances,
        base_rewards,
    )
    # 2. Process rewards and penalties for crosslinks
    crosslinks_rewards, crosslinks_penalties = _process_rewards_and_penalties_for_crosslinks(
        state,
        config,
        effective_balances,
        base_rewards,
    )

    # Apply the overall rewards/penalties
    for index in range(len(state.validator_registry)):
        state = state.update_validator_balance(
            ValidatorIndex(index),
            # Prevent validator balance under flow
            max(
                (
                    state.validator_balances[index] +
                    finality_rewards[index] +
                    crosslinks_rewards[index] -
                    finality_penalties[index] -
                    crosslinks_penalties[index]
                ),
                0,
            ),
        )

    return state


#
# Ejections
#
def process_ejections(state: BeaconState,
                      config: Eth2Config) -> BeaconState:
    """
    Iterate through the validator registry and eject active validators
    with balance below ``EJECTION_BALANCE``.
    """
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        state.current_epoch(config.SLOTS_PER_EPOCH),
    )
    for index in set(active_validator_indices):
        if state.validator_balances[index] < config.EJECTION_BALANCE:
            state = exit_validator(
                state,
                index,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
            )
    return state


#
# Validator registry and shuffling seed data
#
def _update_previous_shuffling_data(state: BeaconState) -> BeaconState:
    return state.copy(
        previous_shuffling_epoch=state.current_shuffling_epoch,
        previous_shuffling_start_shard=state.current_shuffling_start_shard,
        previous_shuffling_seed=state.current_shuffling_seed,
    )


def _check_if_update_validator_registry(state: BeaconState,
                                        config: Eth2Config) -> Tuple[bool, int]:
    if state.finalized_epoch <= state.validator_registry_update_epoch:
        return False, 0

    current_epoch_committee_count = get_current_epoch_committee_count(
        state,
        shard_count=config.SHARD_COUNT,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
        target_committee_size=config.TARGET_COMMITTEE_SIZE,
    )

    # Get every shard in the current committees
    shards = set(
        (state.current_shuffling_start_shard + i) % config.SHARD_COUNT
        for i in range(current_epoch_committee_count)
    )
    for shard in shards:
        if state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch:
            return False, 0

    return True, current_epoch_committee_count


def _update_shuffling_epoch(state: BeaconState, slots_per_epoch: int) -> BeaconState:
    """
    Updates the ``current_shuffling_epoch`` to the ``state``'s next epoch.
    """
    return state.copy(
        current_shuffling_epoch=state.next_epoch(slots_per_epoch),
    )


def _update_shuffling_start_shard(state: BeaconState,
                                  current_epoch_committee_count: int,
                                  shard_count: int) -> BeaconState:
    """
    Updates the ``current_shuffling_start_shard`` to the current value in
    the ``state`` incremented by the number of shards we touched in the current epoch.
    """
    return state.copy(
        current_shuffling_start_shard=(
            state.current_shuffling_start_shard + current_epoch_committee_count
        ) % shard_count,
    )


def _update_shuffling_seed(state: BeaconState,
                           committee_config: CommitteeConfig) -> BeaconState:
    """
    Updates the ``current_shuffling_seed`` in the ``state`` given the current state data.
    """
    # The `helpers.generate_seed` function is only present to provide an entry point
    # for mocking this out in tests.
    current_shuffling_seed = helpers.generate_seed(
        state=state,
        epoch=state.current_shuffling_epoch,
        committee_config=committee_config,
    )
    return state.copy(
        current_shuffling_seed=current_shuffling_seed,
    )


def _is_ready_to_activate(state: BeaconState,
                          index: ValidatorIndex,
                          max_deposit_amount: Gwei) -> bool:
    validator = state.validator_registry[index]
    balance = state.validator_balances[index]
    return validator.activation_epoch == FAR_FUTURE_EPOCH and balance >= max_deposit_amount


def _is_ready_to_exit(state: BeaconState, index: ValidatorIndex) -> bool:
    validator = state.validator_registry[index]
    return validator.exit_epoch == FAR_FUTURE_EPOCH and validator.initiated_exit


def _churn_validators(state: BeaconState,
                      config: Eth2Config,
                      check_should_churn_fn: Callable[..., Any],
                      churn_fn: Callable[..., Any],
                      max_balance_churn: int) -> BeaconState:
    """
    Churn the validators. The number of the churning validators is based on
    the given ``max_balance_churn``.

    :param check_should_churn_fn: the funcation to determine if the validator should be churn
    :param churn_fn``: the function to churn the validators; it could be ``activate_validator`` or
    ``exit_validator``
    """
    balance_churn = 0
    for index in range(len(state.validator_registry)):
        index = ValidatorIndex(index)
        should_churn = check_should_churn_fn(
            state,
            index,
        )
        if should_churn:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(
                state.validator_balances,
                index,
                config.MAX_DEPOSIT_AMOUNT,
            )
            if balance_churn > max_balance_churn:
                break

            state = churn_fn(state, index)
    return state


def update_validator_registry(state: BeaconState, config: Eth2Config) -> BeaconState:
    """
    Update validator registry.
    """
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    # The active validators
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    # The total effective balance of active validators
    total_balance = get_total_balance(
        state.validator_balances,
        active_validator_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )

    # The maximum balance churn in Gwei (for deposits and exits separately)
    max_balance_churn = max(
        config.MAX_DEPOSIT_AMOUNT,
        total_balance // (2 * config.MAX_BALANCE_CHURN_QUOTIENT)
    )

    # Activate validators within the allowable balance churn
    # linter didn't like a bare lambda
    state = _churn_validators(
        state=state,
        config=config,
        check_should_churn_fn=lambda state, index: _is_ready_to_activate(
            state,
            index,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
        ),
        churn_fn=lambda state, index: activate_validator(
            state,
            index,
            is_genesis=False,
            genesis_epoch=config.GENESIS_EPOCH,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
        ),
        max_balance_churn=max_balance_churn,
    )

    # Exit validators within the allowable balance churn
    # linter didn't like a bare lambda
    state = _churn_validators(
        state=state,
        config=config,
        check_should_churn_fn=lambda state, index: _is_ready_to_exit(state, index),
        churn_fn=lambda state, index: exit_validator(
            state,
            index,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
        ),
        max_balance_churn=max_balance_churn,
    )

    state = state.copy(
        validator_registry_update_epoch=current_epoch,
    )

    return state


StateUpdaterForConfig = Callable[[BeaconState, Eth2Config], BeaconState]


@curry
def _process_validator_registry_with_update(current_epoch_committee_count: int,
                                            state: BeaconState,
                                            config: Eth2Config) -> StateUpdaterForConfig:
    state = update_validator_registry(state, config)

    # Update step-by-step since updated `state.current_shuffling_epoch`
    # is used to calculate other value). Follow the spec tightly now.
    state = _update_shuffling_start_shard(state, current_epoch_committee_count, config.SHARD_COUNT)

    state = _update_shuffling_epoch(state, config.SLOTS_PER_EPOCH)

    state = _update_shuffling_seed(state, CommitteeConfig(config))

    return state


def _process_validator_registry_without_update(state: BeaconState,
                                               config: Eth2Config) -> BeaconState:
    epochs_since_last_registry_update = (
        state.current_epoch(config.SLOTS_PER_EPOCH) - state.validator_registry_update_epoch
    )

    if epochs_since_last_registry_update <= 1:
        return state

    if is_power_of_two(epochs_since_last_registry_update):
        # Update step-by-step since updated `state.current_shuffling_epoch`
        # is used to calculate other value). Follow the spec tightly now.
        state = _update_shuffling_epoch(state, config.SLOTS_PER_EPOCH)

        # NOTE: We do NOT update the "start shard" as we have not
        # produced a full set of new crosslinks; validators should have a chance to
        # complete this goal in future epochs.

        state = _update_shuffling_seed(state, CommitteeConfig(config))

    return state


def process_validator_registry(state: BeaconState,
                               config: Eth2Config) -> BeaconState:
    state = _update_previous_shuffling_data(state)

    need_to_update, current_epoch_committee_count = _check_if_update_validator_registry(
        state,
        config
    )

    if need_to_update:
        # this next function call returns a closure, linter didn't like a bare lambda
        validator_registry_transition = _process_validator_registry_with_update(
            current_epoch_committee_count,
        )
    else:
        validator_registry_transition = _process_validator_registry_without_update

    state = validator_registry_transition(state, config)

    state = process_slashings(state, config)

    state = process_exit_queue(state, config)

    return state


def _update_latest_active_index_roots(state: BeaconState,
                                      committee_config: CommitteeConfig) -> BeaconState:
    """
    Return the BeaconState with updated `latest_active_index_roots`.
    """
    next_epoch = state.next_epoch(committee_config.SLOTS_PER_EPOCH)

    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        Epoch(next_epoch + committee_config.ACTIVATION_EXIT_DELAY),
    )
    index_root = ssz.hash_tree_root(
        active_validator_indices,
        ssz.sedes.List(ssz.uint64),
    )

    latest_active_index_roots = update_tuple_item(
        state.latest_active_index_roots,
        (
            (next_epoch + committee_config.ACTIVATION_EXIT_DELAY) %
            committee_config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH
        ),
        index_root,
    )

    return state.copy(
        latest_active_index_roots=latest_active_index_roots,
    )


def _compute_total_penalties(state: BeaconState,
                             config: Eth2Config,
                             current_epoch: Epoch) -> Gwei:
    epoch_index = current_epoch % config.LATEST_SLASHED_EXIT_LENGTH
    start_index_in_latest_slashed_balances = (
        (epoch_index + 1) % config.LATEST_SLASHED_EXIT_LENGTH
    )
    total_at_start = state.latest_slashed_balances[start_index_in_latest_slashed_balances]
    total_at_end = state.latest_slashed_balances[epoch_index]
    return Gwei(total_at_end - total_at_start)


def _compute_individual_penalty(state: BeaconState,
                                config: Eth2Config,
                                validator_index: ValidatorIndex,
                                total_penalties: Gwei,
                                total_balance: Gwei) -> Gwei:
    effective_balance = get_effective_balance(
        state.validator_balances,
        validator_index,
        config.MAX_DEPOSIT_AMOUNT,
    )
    return Gwei(
        max(
            effective_balance * min(total_penalties * 3, total_balance) // total_balance,
            effective_balance // config.MIN_PENALTY_QUOTIENT,
        )
    )


def process_slashings(state: BeaconState,
                      config: Eth2Config) -> BeaconState:
    """
    Process the slashings.
    """
    latest_slashed_exit_length = config.LATEST_SLASHED_EXIT_LENGTH
    max_deposit_amount = config.MAX_DEPOSIT_AMOUNT

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    total_balance = Gwei(
        sum(
            get_effective_balance(state.validator_balances, i, max_deposit_amount)
            for i in active_validator_indices
        )
    )
    total_penalties = _compute_total_penalties(
        state,
        config,
        current_epoch,
    )

    for validator_index, validator in enumerate(state.validator_registry):
        validator_index = ValidatorIndex(validator_index)
        is_halfway_to_withdrawable_epoch = (
            current_epoch == validator.withdrawable_epoch - latest_slashed_exit_length // 2
        )
        if validator.slashed and is_halfway_to_withdrawable_epoch:
            penalty = _compute_individual_penalty(
                state=state,
                config=config,
                validator_index=validator_index,
                total_penalties=total_penalties,
                total_balance=total_balance,
            )
            state = state.update_validator_balance(
                validator_index=validator_index,
                balance=state.validator_balances[validator_index] - penalty,
            )
    return state


def process_exit_queue(state: BeaconState,
                       config: Eth2Config) -> BeaconState:
    """
    Process the exit queue.
    """
    def eligible(index: ValidatorIndex) -> bool:
        validator = state.validator_registry[index]
        # Filter out dequeued validators
        if validator.withdrawable_epoch != FAR_FUTURE_EPOCH:
            return False
        # Dequeue if the minimum amount of time has passed
        else:
            return (
                state.current_epoch(config.SLOTS_PER_EPOCH) >=
                validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
            )

    eligible_indices = filter(
        eligible,
        tuple([ValidatorIndex(i) for i in range(len(state.validator_registry))])
    )
    # Sort in order of exit epoch, and validators that exit within the same epoch exit
    # in order of validator index
    sorted_indices = sorted(
        eligible_indices,
        key=lambda index: state.validator_registry[index].exit_epoch,
    )
    for dequeues, index in enumerate(sorted_indices):
        if dequeues >= config.MAX_EXIT_DEQUEUES_PER_EPOCH:
            break
        state = prepare_validator_for_withdrawal(
            state,
            ValidatorIndex(index),
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            min_validator_withdrawability_delay=config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY,
        )

    return state


def _update_historical_roots(state: BeaconState,
                             next_epoch: Epoch,
                             config: Eth2Config) -> BeaconState:
    updated_historical_roots = state.historical_roots
    epochs_per_historical_root = config.SLOTS_PER_HISTORICAL_ROOT // config.SLOTS_PER_EPOCH
    should_update_historical_roots = next_epoch % epochs_per_historical_root == 0
    if should_update_historical_roots:
        historical_batch = HistoricalBatch(
            block_roots=state.latest_block_roots,
            state_roots=state.latest_state_roots,
        )
        updated_historical_roots += (historical_batch.root,)

    return state.copy(
        historical_roots=updated_historical_roots
    )


#
# Final updates
#
def process_final_updates(state: BeaconState,
                          config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)

    state = _update_latest_active_index_roots(state, CommitteeConfig(config))

    state = state.copy(
        latest_slashed_balances=update_tuple_item(
            state.latest_slashed_balances,
            next_epoch % config.LATEST_SLASHED_EXIT_LENGTH,
            state.latest_slashed_balances[current_epoch % config.LATEST_SLASHED_EXIT_LENGTH],
        ),
        latest_randao_mixes=update_tuple_item(
            state.latest_randao_mixes,
            next_epoch % config.LATEST_RANDAO_MIXES_LENGTH,
            get_randao_mix(
                state=state,
                epoch=current_epoch,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            ),
        ),
    )

    state = _update_historical_roots(state, next_epoch, config)

    # Rotate current/previous epoch attestations
    state = state.copy(
        previous_epoch_attestations=state.current_epoch_attestations,
        current_epoch_attestations=(),
    )

    return state
