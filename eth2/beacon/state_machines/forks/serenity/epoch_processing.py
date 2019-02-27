from typing import (
    Dict,
    Iterable,
    Sequence,
    Set,
    Tuple,
)

from cytoolz import (
    curry,
    pipe,
)

from eth_utils import (
    to_dict,
    to_tuple,
)

from eth2.beacon import helpers
from eth2._utils.numeric import (
    integer_squareroot,
    is_power_of_two,
)
from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.beacon.exceptions import (
    NoWinningRootError,
)
from eth2.beacon.committee_helpers import (
    get_attester_indices_from_attesttion,
    get_beacon_proposer_index,
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
)
from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.epoch_processing_helpers import (
    get_base_reward,
    get_current_epoch_attestations,
    get_inclusion_infos,
    get_previous_epoch_attestations,
    get_previous_epoch_head_attestations,
    get_winning_root,
    get_total_balance,
    get_total_balance_from_effective_balances,
    get_epoch_boundary_attesting_balances,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_effective_balance,
    get_epoch_start_slot,
    get_randao_mix,
    slot_to_epoch,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.datastructures.inclusion_info import InclusionInfo
from eth2.beacon.datastructures.reward_settlement_context import RewardSettlementContext
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.pending_attestation_records import PendingAttestationRecord
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    SignedGwei,
    ValidatorIndex,
)


#
# Justification
#

def _current_previous_epochs_justifiable(
        state: BeaconState,
        current_epoch: Epoch,
        previous_epoch: Epoch,
        config: BeaconConfig) -> Tuple[bool, bool]:
    """
    Determine if epoch boundary attesting balance is greater than 2/3 of current_total_balance
    for current and previous epochs.
    """

    current_epoch_active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        current_epoch,
    )
    previous_epoch_active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        previous_epoch,
    )
    current_total_balance = get_total_balance(
        state.validator_balances,
        current_epoch_active_validator_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )
    previous_total_balance = get_total_balance(
        state.validator_balances,
        previous_epoch_active_validator_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )

    (
        previous_epoch_boundary_attesting_balance,
        current_epoch_boundary_attesting_balance
    ) = get_epoch_boundary_attesting_balances(current_epoch, previous_epoch, state, config)

    previous_epoch_justifiable = (
        3 * previous_epoch_boundary_attesting_balance >= 2 * previous_total_balance
    )
    current_epoch_justifiable = (
        3 * current_epoch_boundary_attesting_balance >= 2 * current_total_balance
    )
    return current_epoch_justifiable, previous_epoch_justifiable


def _get_finalized_epoch(
        justification_bitfield: int,
        previous_justified_epoch: Epoch,
        justified_epoch: Epoch,
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
        justified_epoch == previous_epoch - 1
    )
    rule_4 = (
        justification_bitfield % 4 == 0b11 and
        justified_epoch == previous_epoch
    )
    # Check the rule in the order that can finalize higher epoch possible
    # The second output indicating what rule triggered is for testing purpose
    if rule_4:
        return justified_epoch, 4
    elif rule_3:
        return justified_epoch, 3
    elif rule_2:
        return previous_justified_epoch, 2
    elif rule_1:
        return previous_justified_epoch, 1
    else:
        return finalized_epoch, 0


def process_justification(state: BeaconState, config: BeaconConfig) -> BeaconState:

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)

    current_epoch_justifiable, previous_epoch_justifiable = _current_previous_epochs_justifiable(
        state,
        current_epoch,
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
        new_justified_epoch = state.justified_epoch

    finalized_epoch, _ = _get_finalized_epoch(
        justification_bitfield,
        state.previous_justified_epoch,
        state.justified_epoch,
        state.finalized_epoch,
        previous_epoch,
    )

    return state.copy(
        previous_justified_epoch=state.justified_epoch,
        justified_epoch=new_justified_epoch,
        justification_bitfield=justification_bitfield,
        finalized_epoch=finalized_epoch,
    )


#
# Crosslinks
#
@to_tuple
def _filter_attestations_by_shard(
        attestations: Sequence[Attestation],
        shard: Shard) -> Iterable[Attestation]:
    for attestation in attestations:
        if attestation.data.shard == shard:
            yield attestation


def process_crosslinks(state: BeaconState, config: BeaconConfig) -> BeaconState:
    """
    Implement 'per-epoch-processing.crosslinks' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#crosslinks

    For each shard from the past two epochs, find the shard block
    root that has been attested to by the most stake.
    If enough(>= 2/3 total stake) attesting stake, update the crosslink record of that shard.
    Return resulting ``state``
    """
    latest_crosslinks = state.latest_crosslinks
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.GENESIS_EPOCH,
    )
    current_epoch_attestations = get_current_epoch_attestations(state, config.SLOTS_PER_EPOCH)
    previous_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH),
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
            try:
                winning_root, total_attesting_balance = get_winning_root(
                    state=state,
                    shard=shard,
                    # Use `_filter_attestations_by_shard` to filter out attestations
                    # not attesting to this shard so we don't need to going over
                    # irrelevent attestations over and over again.
                    attestations=_filter_attestations_by_shard(
                        previous_epoch_attestations + current_epoch_attestations,
                        shard,
                    ),
                    max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
                    committee_config=CommitteeConfig(config),
                )
            except NoWinningRootError:
                # No winning shard block root found for this shard.
                pass
            else:
                total_balance = get_total_balance(
                    state.validator_balances,
                    crosslink_committee,
                    config.MAX_DEPOSIT_AMOUNT,
                )
                if 3 * total_attesting_balance >= 2 * total_balance:
                    latest_crosslinks = update_tuple_item(
                        latest_crosslinks,
                        shard,
                        CrosslinkRecord(
                            epoch=state.current_epoch(config.SLOTS_PER_EPOCH),
                            crosslink_data_root=winning_root,
                        ),
                    )
                else:
                    # Don't update the crosslink of this shard
                    pass
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


def _apply_rewards_and_penalties(
        reward_settlement_context: RewardSettlementContext) -> Tuple[Dict[ValidatorIndex, Gwei], Dict[ValidatorIndex, Gwei]]:  # noqa: E501
    rewards_received = reward_settlement_context.rewards_received
    penalties_received = reward_settlement_context.penalties_received
    for index in reward_settlement_context.indices_to_reward:
        rewards_received = _update_rewards_or_penalies(
            index,
            reward_settlement_context.rewards[index],
            rewards_received,
        )
    for index in reward_settlement_context.indices_to_penalize:
        penalties_received = _update_rewards_or_penalies(
            index,
            reward_settlement_context.penalties[index],
            penalties_received,
        )
    return rewards_received, penalties_received


@curry
def _process_rewards_and_penalties_for_finality(
        state: BeaconState,
        config: BeaconConfig,
        previous_epoch_active_validator_indices: Set[ValidatorIndex],
        previous_total_balance: Gwei,
        previous_epoch_attestations: Sequence[Attestation],
        previous_epoch_attester_indices: Set[ValidatorIndex],
        inclusion_infos: Dict[ValidatorIndex, InclusionInfo],
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei],
        old_rewards_received: Dict[ValidatorIndex, SignedGwei]) -> Dict[ValidatorIndex, SignedGwei]:
    previous_epoch_boundary_attestations = (
        a
        for a in previous_epoch_attestations
        if a.data.epoch_boundary_root == get_block_root(
            state,
            get_epoch_start_slot(
                state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH),
                config.SLOTS_PER_EPOCH,
            ),
            config.LATEST_BLOCK_ROOTS_LENGTH,
        )
    )
    previous_epoch_boundary_attester_indices = get_attester_indices_from_attesttion(
        state=state,
        attestations=previous_epoch_boundary_attestations,
        committee_config=CommitteeConfig(config),
    )

    previous_epoch_head_attestations = get_previous_epoch_head_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.GENESIS_EPOCH,
        config.LATEST_BLOCK_ROOTS_LENGTH,
    )
    previous_epoch_head_attester_indices = get_attester_indices_from_attesttion(
        state=state,
        attestations=previous_epoch_head_attestations,
        committee_config=CommitteeConfig(config),
    )

    rewards_received = {
        index: Gwei(0)
        for index in old_rewards_received
    }
    penalties_received = rewards_received.copy()
    epochs_since_finality = state.next_epoch(config.SLOTS_PER_EPOCH) - state.finalized_epoch
    if epochs_since_finality <= 4:
        # 1.1 Expected FFG source:
        previous_epoch_attesting_balance = get_total_balance_from_effective_balances(
            effective_balances,
            previous_epoch_attester_indices,
        )
        # Reward validators in `previous_epoch_attester_indices`
        # # Punish active validators not in `previous_epoch_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_attester_indices,
        )
        rewards = {
            index: Gwei(
                base_rewards[index] *
                previous_epoch_attesting_balance //
                previous_total_balance
            )
            for index in previous_epoch_attester_indices
        }
        penalties = {
            index: base_rewards[index]
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                rewards=rewards,
                indices_to_reward=previous_epoch_attester_indices,
                penalties=penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # 1.2 Expected FFG target:
        previous_epoch_boundary_attesting_balance = get_total_balance_from_effective_balances(
            effective_balances,
            previous_epoch_boundary_attester_indices,
        )
        # Reward validators in `previous_epoch_boundary_attester_indices`
        # Punish active validators not in `previous_epoch_boundary_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_boundary_attester_indices,
        )
        rewards = {
            index: Gwei(
                base_rewards[index] *
                previous_epoch_boundary_attesting_balance //
                previous_total_balance
            )
            for index in previous_epoch_boundary_attester_indices
        }
        penalties = {
            index: base_rewards[index]
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                rewards=rewards,
                indices_to_reward=previous_epoch_boundary_attester_indices,
                penalties=penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # 1.3 Expected beacon chain head:
        previous_epoch_head_attesting_balance = get_total_balance_from_effective_balances(
            effective_balances,
            previous_epoch_head_attester_indices,
        )
        # Reward validators in `previous_epoch_head_attester_indices`
        # Punish active validators not in `previous_epoch_head_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_head_attester_indices,
        )
        rewards = {
            index: Gwei(
                base_rewards[index] *
                previous_epoch_head_attesting_balance //
                previous_total_balance
            )
            for index in previous_epoch_head_attester_indices
        }
        penalties = {
            index: base_rewards[index]
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                rewards=rewards,
                indices_to_reward=previous_epoch_head_attester_indices,
                penalties=penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # 1.4 Inclusion distance:
        # Reward validators in `previous_epoch_attester_indices`
        rewards = {
            index: Gwei(
                base_rewards[index] *
                config.MIN_ATTESTATION_INCLUSION_DELAY //
                inclusion_infos[index].inclusion_distance
            )
            for index in previous_epoch_attester_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                rewards=rewards,
                indices_to_reward=previous_epoch_attester_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

    # epochs_since_finality > 4
    else:
        # Punish active validators not in `previous_epoch_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_attester_indices,
        )
        inactivity_penalties = {
            index: base_rewards[index] + (
                effective_balances[index] *
                epochs_since_finality // config.INACTIVITY_PENALTY_QUOTIENT // 2
            )
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                penalties=inactivity_penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # Punish active validators not in `previous_epoch_boundary_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_boundary_attester_indices,
        )
        inactivity_penalties = {
            index: base_rewards[index] + (
                effective_balances[index] *
                epochs_since_finality // config.INACTIVITY_PENALTY_QUOTIENT // 2
            )
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                penalties=inactivity_penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # Punish active validators not in `previous_epoch_head_attester_indices`
        excluded_active_validators_indices = previous_epoch_active_validator_indices.difference(
            previous_epoch_head_attester_indices,
        )
        penalties = {
            index: base_rewards[index]
            for index in excluded_active_validators_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                penalties=penalties,
                indices_to_penalize=excluded_active_validators_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # Punish penalized active validators
        current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
        penalties = {
            index: 3 * base_rewards[index] + 2 * (
                effective_balances[index] *
                epochs_since_finality //
                config.INACTIVITY_PENALTY_QUOTIENT // 2
            )
            for index in previous_epoch_active_validator_indices
            if state.validator_registry[index].slashed_epoch <= current_epoch
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                penalties=penalties,
                indices_to_penalize={index for index in penalties},
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

        # Punish validators in `previous_epoch_attester_indices`
        penalties = {
            index: Gwei(
                base_rewards[index] - (
                    base_rewards[index] *
                    config.MIN_ATTESTATION_INCLUSION_DELAY //
                    inclusion_infos[index].inclusion_distance
                )
            )
            for index in previous_epoch_attester_indices
        }
        rewards_received, penalties_received = _apply_rewards_and_penalties(
            RewardSettlementContext(
                penalties=penalties,
                indices_to_penalize=previous_epoch_attester_indices,
                rewards_received=rewards_received,
                penalties_received=penalties_received,
            ),
        )

    historical_rewards_received = old_rewards_received.copy()
    for index in rewards_received:
        historical_rewards_received = _update_rewards_or_penalies(
            index,
            rewards_received[index] - penalties_received[index],
            historical_rewards_received,
        )
    return historical_rewards_received


@curry
def _process_rewards_and_penalties_for_attestation_inclusion(
        state: BeaconState,
        config: BeaconConfig,
        previous_epoch_attester_indices: Set[ValidatorIndex],
        inclusion_infos: Dict[ValidatorIndex, InclusionInfo],
        base_rewards: Dict[ValidatorIndex, Gwei],
        old_rewards_received: Dict[ValidatorIndex, SignedGwei]) -> Dict[ValidatorIndex, SignedGwei]:
    rewards_received = old_rewards_received.copy()
    for index in previous_epoch_attester_indices:
        proposer_index = get_beacon_proposer_index(
            state,
            inclusion_infos[index].inclusion_slot,
            CommitteeConfig(config),
        )
        reward = base_rewards[index] // config.ATTESTATION_INCLUSION_REWARD_QUOTIENT
        rewards_received[proposer_index] = SignedGwei(rewards_received[proposer_index] + reward)
    return rewards_received


@curry
def _process_rewards_and_penalties_for_crosslinks(
        state: BeaconState,
        config: BeaconConfig,
        previous_epoch_attestations: Iterable[PendingAttestationRecord],
        effective_balances: Dict[ValidatorIndex, Gwei],
        base_rewards: Dict[ValidatorIndex, Gwei],
        old_rewards_received: Dict[ValidatorIndex, SignedGwei]) -> Dict[ValidatorIndex, SignedGwei]:
    rewards_received = old_rewards_received.copy()
    previous_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    current_epoch_start_slot = get_epoch_start_slot(
        state.current_epoch(config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    # Also need current epoch attestations to compute the winning root.
    current_epoch_attestations = get_current_epoch_attestations(state, config.SLOTS_PER_EPOCH)
    for slot in range(previous_epoch_start_slot, current_epoch_start_slot):
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )
        for crosslink_committee, shard in crosslink_committees_at_slot:
            filtered_attestations = _filter_attestations_by_shard(
                previous_epoch_attestations + current_epoch_attestations,
                shard,
            )
            try:
                winning_root, total_attesting_balance = get_winning_root(
                    state=state,
                    shard=shard,
                    attestations=filtered_attestations,
                    max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
                    committee_config=CommitteeConfig(config),
                )
            except NoWinningRootError:
                # No winning shard block root found for this shard.
                # Hence no one is counted as attesting validator.
                attesting_validator_indices: Iterable[ValidatorIndex] = set()
            else:
                attesting_validator_indices = get_attester_indices_from_attesttion(
                    state=state,
                    attestations=(
                        a
                        for a in filtered_attestations
                        if a.data.shard == shard and a.data.crosslink_data_root == winning_root
                    ),
                    committee_config=CommitteeConfig(config),
                )
            total_balance = get_total_balance_from_effective_balances(
                effective_balances,
                crosslink_committee,
            )
            for index in attesting_validator_indices:
                reward = base_rewards[index] * total_attesting_balance // total_balance
                rewards_received[index] = SignedGwei(rewards_received[index] + reward)
            for index in set(crosslink_committee).difference(attesting_validator_indices):
                penalty = base_rewards[index]
                rewards_received[index] = SignedGwei(rewards_received[index] - penalty)
    return rewards_received


def process_rewards_and_penalties(state: BeaconState, config: BeaconConfig) -> BeaconState:
    # Compute previous epoch active validator indices and the total balance they account for
    # for later use.
    previous_epoch_active_validator_indices = set(
        get_active_validator_indices(
            state.validator_registry,
            state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
        )
    )
    previous_total_balance: Gwei = get_total_balance(
        state.validator_balances,
        tuple(previous_epoch_active_validator_indices),
        config.MAX_DEPOSIT_AMOUNT,
    )

    # Compute previous epoch attester indices and the total balance they account for
    # for later use.
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.GENESIS_EPOCH,
    )
    previous_epoch_attester_indices = get_attester_indices_from_attesttion(
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
        index: get_effective_balance(
            state.validator_balances,
            index,
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in previous_epoch_active_validator_indices
    }
    # Compute base reward of each previous epoch active validator for later use
    _base_reward_quotient = (
        integer_squareroot(previous_total_balance) // config.BASE_REWARD_QUOTIENT
    )
    base_rewards = {
        index: get_base_reward(
            state=state,
            index=index,
            base_reward_quotient=_base_reward_quotient,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
        )
        for index in previous_epoch_active_validator_indices
    }

    # Initialize the reward (validator) received map
    rewards_received = {
        index: SignedGwei(0)
        for index in previous_epoch_active_validator_indices
    }

    # 1. Process rewards and penalties for justification and finalization
    rewards_received = pipe(
        rewards_received,
        _process_rewards_and_penalties_for_finality(
            state,
            config,
            previous_epoch_active_validator_indices,
            previous_total_balance,
            previous_epoch_attestations,
            previous_epoch_attester_indices,
            inclusion_infos,
            effective_balances,
            base_rewards,
        ),
        _process_rewards_and_penalties_for_attestation_inclusion(
            state,
            config,
            previous_epoch_attester_indices,
            inclusion_infos,
            base_rewards,
        ),
        _process_rewards_and_penalties_for_crosslinks(
            state,
            config,
            previous_epoch_attestations,
            effective_balances,
            base_rewards,
        )
    )

    # Apply the overall rewards/penalties
    for index in previous_epoch_active_validator_indices:
        state = state.update_validator_balance(
            index,
            # Prevent validator balance under flow
            max(state.validator_balances[index] + rewards_received[index], 0),
        )

    return state


#
# Validator registry and shuffling seed data
#
def _check_if_update_validator_registry(state: BeaconState,
                                        config: BeaconConfig) -> Tuple[bool, int]:
    if state.finalized_epoch <= state.validator_registry_update_epoch:
        return False, 0

    num_shards_in_committees = get_current_epoch_committee_count(
        state,
        shard_count=config.SHARD_COUNT,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
        target_committee_size=config.TARGET_COMMITTEE_SIZE,
    )

    # Get every shard in the current committees
    shards = set(
        (state.current_shuffling_start_shard + i) % config.SHARD_COUNT
        for i in range(num_shards_in_committees)
    )
    for shard in shards:
        if state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch:
            return False, 0

    return True, num_shards_in_committees


def update_validator_registry(state: BeaconState) -> BeaconState:
    # TODO
    return state


def process_validator_registry(state: BeaconState,
                               config: BeaconConfig) -> BeaconState:
    state = state.copy(
        previous_shuffling_epoch=state.current_shuffling_epoch,
        previous_shuffling_start_shard=state.current_shuffling_start_shard,
        previous_shuffling_seed=state.current_shuffling_seed,
    )

    need_to_update, num_shards_in_committees = _check_if_update_validator_registry(state, config)

    if need_to_update:
        state = update_validator_registry(state)

        # Update step-by-step since updated `state.current_shuffling_epoch`
        # is used to calculate other value). Follow the spec tightly now.
        state = state.copy(
            current_shuffling_epoch=state.next_epoch(config.SLOTS_PER_EPOCH),
        )
        state = state.copy(
            current_shuffling_start_shard=(
                state.current_shuffling_start_shard + num_shards_in_committees
            ) % config.SHARD_COUNT,
        )

        # The `helpers.generate_seed` function is only present to provide an entry point
        # for mocking this out in tests.
        current_shuffling_seed = helpers.generate_seed(
            state=state,
            epoch=state.current_shuffling_epoch,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            min_seed_lookahead=config.MIN_SEED_LOOKAHEAD,
            activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
            latest_active_index_roots_length=config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,
            latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
        )
        state = state.copy(
            current_shuffling_seed=current_shuffling_seed,
        )
    else:
        epochs_since_last_registry_change = (
            state.current_epoch(config.SLOTS_PER_EPOCH) - state.validator_registry_update_epoch
        )
        if is_power_of_two(epochs_since_last_registry_change):
            # Update step-by-step since updated `state.current_shuffling_epoch`
            # is used to calculate other value). Follow the spec tightly now.
            state = state.copy(
                current_shuffling_epoch=state.next_epoch(config.SLOTS_PER_EPOCH),
            )

            # The `helpers.generate_seed` function is only present to provide an entry point
            # for mocking this out in tests.
            current_shuffling_seed = helpers.generate_seed(
                state=state,
                epoch=state.current_shuffling_epoch,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                min_seed_lookahead=config.MIN_SEED_LOOKAHEAD,
                activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
                latest_active_index_roots_length=config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            )
            state = state.copy(
                current_shuffling_seed=current_shuffling_seed,
            )
        else:
            pass

    return state


#
# Final updates
#
def _update_latest_active_index_roots(state: BeaconState,
                                      committee_config: CommitteeConfig) -> BeaconState:
    """
    Return the BeaconState with updated `latest_active_index_roots`.
    """
    next_epoch = state.next_epoch(committee_config.SLOTS_PER_EPOCH)

    # TODO: chanege to hash_tree_root
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        Epoch(next_epoch + committee_config.ACTIVATION_EXIT_DELAY),
    )
    index_root = hash_eth2(
        b''.join(
            [
                index.to_bytes(32, 'big')
                for index in active_validator_indices
            ]
        )
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


def process_final_updates(state: BeaconState,
                          config: BeaconConfig) -> BeaconState:
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
            next_epoch % config.LATEST_SLASHED_EXIT_LENGTH,
            get_randao_mix(
                state=state,
                epoch=current_epoch,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            ),
        ),
    )

    latest_attestations = tuple(
        filter(
            lambda attestation: (
                slot_to_epoch(attestation.data.slot, config.SLOTS_PER_EPOCH) >= current_epoch
            ),
            state.latest_attestations
        )
    )
    state = state.copy(
        latest_attestations=latest_attestations,
    )

    return state
