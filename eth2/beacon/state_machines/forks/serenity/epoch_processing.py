from typing import (
    Sequence,
    Tuple,
)

from eth_utils.toolz import (
    curry,
)
import ssz

from eth_typing import (
    Hash32,
)

from eth2._utils.tuple import (
    update_tuple_item,
    update_tuple_item_with_fn,
)
from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)
from eth2.beacon.constants import (
    BASE_REWARDS_PER_EPOCH,
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committee,
    get_epoch_committee_count,
    get_epoch_start_shard,
    get_shard_delta,
)
from eth2.beacon.epoch_processing_helpers import (
    decrease_balance,
    get_attesting_balance,
    get_attesting_indices,
    get_base_reward,
    get_churn_limit,
    get_delayed_activation_exit_epoch,
    get_matching_head_attestations,
    get_matching_source_attestations,
    get_matching_target_attestations,
    get_total_active_balance,
    get_total_balance,
    get_unslashed_attesting_indices,
    get_winning_crosslink_and_attesting_indices,
    increase_balance,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_randao_mix,
)
from eth2.beacon.validator_status_helpers import (
    initiate_exit_for_validator,
)
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.historical_batch import HistoricalBatch
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    ValidatorIndex,
)


def _bft_threshold_met(participation: Gwei, total: Gwei) -> bool:
    return 3 * participation >= 2 * total


def _is_threshold_met_against_active_set(state: BeaconState,
                                         attestations: Sequence[PendingAttestation],
                                         config: Eth2Config) -> bool:
    """
    Predicate indicating if the balance at risk of validators making an attestation
    in ``attestations`` is greater than the fault tolerance threshold of the total balance.
    """
    attesting_balance = get_attesting_balance(
        state,
        attestations,
        config
    )

    total_balance = get_total_active_balance(state, config)

    return _bft_threshold_met(
        attesting_balance,
        total_balance,
    )


def _is_epoch_justifiable(state: BeaconState, epoch: Epoch, config: Eth2Config) -> bool:
    attestations = get_matching_target_attestations(
        state,
        epoch,
        config,
    )
    return _is_threshold_met_against_active_set(
        state,
        attestations,
        config,
    )


def _determine_updated_justification_data(justified_epoch: Epoch,
                                          bitfield: int,
                                          is_epoch_justifiable: bool,
                                          candidate_epoch: Epoch,
                                          bit_offset: int) -> Tuple[Epoch, int]:
    if is_epoch_justifiable:
        return (
            candidate_epoch,
            bitfield | (1 << bit_offset),
        )
    else:
        return (
            justified_epoch,
            bitfield,
        )


def _determine_updated_justifications(
        previous_epoch_justifiable: bool,
        previous_epoch: Epoch,
        current_epoch_justifiable: bool,
        current_epoch: Epoch,
        justified_epoch: Epoch,
        justification_bitfield: int) -> Tuple[Epoch, int]:
    (
        justified_epoch,
        justification_bitfield,
    ) = _determine_updated_justification_data(
        justified_epoch,
        justification_bitfield,
        previous_epoch_justifiable,
        previous_epoch,
        1,
    )

    (
        justified_epoch,
        justification_bitfield,
    ) = _determine_updated_justification_data(
        justified_epoch,
        justification_bitfield,
        current_epoch_justifiable,
        current_epoch,
        0,
    )

    return (
        justified_epoch,
        justification_bitfield,
    )


def _determine_new_justified_epoch_and_bitfield(state: BeaconState,
                                                config: Eth2Config) -> Tuple[Epoch, int]:
    genesis_epoch = config.GENESIS_EPOCH
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, genesis_epoch)
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    previous_epoch_justifiable = _is_epoch_justifiable(
        state,
        previous_epoch,
        config,
    )
    current_epoch_justifiable = _is_epoch_justifiable(
        state,
        current_epoch,
        config,
    )

    (
        new_current_justified_epoch,
        justification_bitfield,
    ) = _determine_updated_justifications(
        previous_epoch_justifiable,
        previous_epoch,
        current_epoch_justifiable,
        current_epoch,
        state.current_justified_epoch,
        state.justification_bitfield << 1,
    )

    return (
        new_current_justified_epoch,
        justification_bitfield,
    )


def _determine_new_justified_checkpoint_and_bitfield(
        state: BeaconState,
        config: Eth2Config) -> Tuple[Epoch, Hash32, int]:

    (
        new_current_justified_epoch,
        justification_bitfield,
    ) = _determine_new_justified_epoch_and_bitfield(
        state,
        config,
    )

    new_current_justified_root = get_block_root(
        state,
        new_current_justified_epoch,
        config.SLOTS_PER_EPOCH,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    return (
        new_current_justified_epoch,
        new_current_justified_root,
        justification_bitfield,
    )


# NOTE: the type of bitfield here is an ``int``, to facilitate bitwise operations;
# we do not use the ``Bitfield`` type seen elsewhere.
def _bitfield_matches(bitfield: int,
                      offset: int,
                      modulus: int,
                      pattern: int) -> bool:
    return (bitfield >> offset) % modulus == pattern


def _determine_new_finalized_epoch(last_finalized_epoch: Epoch,
                                   previous_justified_epoch: Epoch,
                                   current_justified_epoch: Epoch,
                                   current_epoch: Epoch,
                                   justification_bitfield: int) -> Epoch:
    new_finalized_epoch = last_finalized_epoch

    if _bitfield_matches(
            justification_bitfield,
            1,
            8,
            0b111,
    ) and previous_justified_epoch + 3 == current_epoch:
        new_finalized_epoch = previous_justified_epoch

    if _bitfield_matches(
            justification_bitfield,
            1,
            4,
            0b11,
    ) and previous_justified_epoch + 2 == current_epoch:
        new_finalized_epoch = previous_justified_epoch

    if _bitfield_matches(
            justification_bitfield,
            0,
            8,
            0b111,
    ) and current_justified_epoch + 2 == current_epoch:
        new_finalized_epoch = current_justified_epoch

    if _bitfield_matches(
            justification_bitfield,
            0,
            4,
            0b11,
    ) and current_justified_epoch + 1 == current_epoch:
        new_finalized_epoch = current_justified_epoch

    return new_finalized_epoch


def _determine_new_finalized_checkpoint(state: BeaconState,
                                        justification_bitfield: int,
                                        config: Eth2Config) -> Tuple[Epoch, Hash32]:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    new_finalized_epoch = _determine_new_finalized_epoch(
        state.finalized_epoch,
        state.previous_justified_epoch,
        state.current_justified_epoch,
        current_epoch,
        justification_bitfield,
    )
    if new_finalized_epoch != state.finalized_epoch:
        # NOTE: we only want to call ``get_block_root``
        # upon some change, not unconditionally
        # Given the way it reads the block roots, it can cause
        # validation problems with some configurations, esp. in testing.
        # This is implicitly happening above for the justified roots.
        new_finalized_root = get_block_root(
            state,
            new_finalized_epoch,
            config.SLOTS_PER_EPOCH,
            config.SLOTS_PER_HISTORICAL_ROOT,
        )
    else:
        new_finalized_root = state.finalized_root

    return (
        new_finalized_epoch,
        new_finalized_root,
    )


def process_justification_and_finalization(state: BeaconState, config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    genesis_epoch = config.GENESIS_EPOCH

    if current_epoch <= genesis_epoch + 1:
        return state

    (
        new_current_justified_epoch,
        new_current_justified_root,
        justification_bitfield,
    ) = _determine_new_justified_checkpoint_and_bitfield(
        state,
        config,
    )

    (
        new_finalized_epoch,
        new_finalized_root,
    ) = _determine_new_finalized_checkpoint(
        state,
        justification_bitfield,
        config,
    )

    return state.copy(
        previous_justified_epoch=state.current_justified_epoch,
        previous_justified_root=state.current_justified_root,
        current_justified_epoch=new_current_justified_epoch,
        current_justified_root=new_current_justified_root,
        justification_bitfield=justification_bitfield,
        finalized_epoch=new_finalized_epoch,
        finalized_root=new_finalized_root,
    )


def _is_threshold_met_against_committee(state: BeaconState,
                                        attesting_indices: Sequence[ValidatorIndex],
                                        committee: Sequence[ValidatorIndex]) -> bool:
    total_attesting_balance = get_total_balance(
        state,
        attesting_indices,
    )
    total_committee_balance = get_total_balance(
        state,
        committee,
    )
    return _bft_threshold_met(total_attesting_balance, total_committee_balance)


def process_crosslinks(state: BeaconState, config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)

    new_current_crosslinks = state.current_crosslinks

    for epoch in (previous_epoch, current_epoch):
        active_validators_indices = get_active_validator_indices(state.validators, epoch)
        epoch_committee_count = get_epoch_committee_count(
            len(active_validators_indices),
            config.SHARD_COUNT,
            config.SLOTS_PER_EPOCH,
            config.TARGET_COMMITTEE_SIZE,
        )
        epoch_start_shard = get_epoch_start_shard(
            state,
            epoch,
            CommitteeConfig(config),
        )
        for shard_offset in range(epoch_committee_count):
            shard = Shard((epoch_start_shard + shard_offset) % config.SHARD_COUNT)
            crosslink_committee = get_crosslink_committee(
                state,
                epoch,
                shard,
                CommitteeConfig(config),
            )

            if not crosslink_committee:
                # empty crosslink committee this epoch
                continue

            winning_crosslink, attesting_indices = get_winning_crosslink_and_attesting_indices(
                state=state,
                epoch=epoch,
                shard=shard,
                config=config,
            )
            threshold_met = _is_threshold_met_against_committee(
                state,
                attesting_indices,
                crosslink_committee,
            )
            if threshold_met:
                new_current_crosslinks = update_tuple_item(
                    new_current_crosslinks,
                    shard,
                    winning_crosslink,
                )

    return state.copy(
        previous_crosslinks=state.current_crosslinks,
        current_crosslinks=new_current_crosslinks,
    )


def get_attestation_deltas(state: BeaconState,
                           config: Eth2Config) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    committee_config = CommitteeConfig(config)
    rewards = tuple(
        0 for _ in range(len(state.validators))
    )
    penalties = tuple(
        0 for _ in range(len(state.validators))
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    total_balance = get_total_active_balance(state, config)
    eligible_validator_indices = tuple(
        ValidatorIndex(index) for index, v in enumerate(state.validators)
        if v.is_active(previous_epoch) or (
            v.slashed and previous_epoch + 1 < v.withdrawable_epoch
        )
    )

    matching_source_attestations = get_matching_source_attestations(
        state,
        previous_epoch,
        config,
    )
    matching_target_attestations = get_matching_target_attestations(
        state,
        previous_epoch,
        config,
    )
    matching_head_attestations = get_matching_head_attestations(
        state,
        previous_epoch,
        config,
    )

    for attestations in (
            matching_source_attestations,
            matching_target_attestations,
            matching_head_attestations
    ):
        unslashed_attesting_indices = get_unslashed_attesting_indices(
            state,
            attestations,
            committee_config,
        )
        attesting_balance = get_total_balance(state, unslashed_attesting_indices)
        for index in eligible_validator_indices:
            if index in unslashed_attesting_indices:
                rewards = update_tuple_item_with_fn(
                    rewards,
                    index,
                    lambda balance, delta: balance + delta,
                    get_base_reward(
                        state,
                        index,
                        config,
                    ) * attesting_balance // total_balance,
                )
            else:
                penalties = update_tuple_item_with_fn(
                    penalties,
                    index,
                    lambda balance, delta: balance + delta,
                    get_base_reward(
                        state,
                        index,
                        config,
                    ),
                )

    for index in get_unslashed_attesting_indices(
            state,
            matching_source_attestations,
            committee_config,
    ):
        attestation = min(
            (
                a for a in matching_source_attestations
                if index in get_attesting_indices(
                    state,
                    a.data,
                    a.aggregation_bitfield,
                    committee_config,
                )
            ),
            key=lambda a: a.inclusion_delay,
        )
        base_reward = get_base_reward(state, index, config)
        proposer_reward = base_reward // config.PROPOSER_REWARD_QUOTIENT
        rewards = update_tuple_item_with_fn(
            rewards,
            attestation.proposer_index,
            lambda balance, delta: balance + delta,
            proposer_reward,
        )
        max_attester_reward = base_reward - proposer_reward
        rewards = update_tuple_item_with_fn(
            rewards,
            index,
            lambda balance, delta: balance + delta,
            (
                max_attester_reward *
                config.MIN_ATTESTATION_INCLUSION_DELAY //
                attestation.inclusion_delay
            )
        )

    finality_delay = previous_epoch - state.finalized_epoch
    if finality_delay > config.MIN_EPOCHS_TO_INACTIVITY_PENALTY:
        matching_target_attesting_indices = get_unslashed_attesting_indices(
            state,
            matching_target_attestations,
            committee_config,
        )
        for index in eligible_validator_indices:
            penalties = update_tuple_item_with_fn(
                penalties,
                index,
                lambda balance, delta: balance + delta,
                BASE_REWARDS_PER_EPOCH * get_base_reward(
                    state,
                    index,
                    config,
                ),
            )
            if index not in matching_target_attesting_indices:
                effective_balance = state.validators[index].effective_balance
                penalties = update_tuple_item_with_fn(
                    penalties,
                    index,
                    lambda balance, delta: balance + delta,
                    effective_balance * finality_delay // config.INACTIVITY_PENALTY_QUOTIENT,
                )
    return tuple(
        Gwei(reward) for reward in rewards
    ), tuple(
        Gwei(penalty) for penalty in penalties
    )


def get_crosslink_deltas(state: BeaconState,
                         config: Eth2Config) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = tuple(
        0 for _ in range(len(state.validators))
    )
    penalties = tuple(
        0 for _ in range(len(state.validators))
    )
    epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    active_validators_indices = get_active_validator_indices(state.validators, epoch)
    epoch_committee_count = get_epoch_committee_count(
        len(active_validators_indices),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )
    epoch_start_shard = get_epoch_start_shard(
        state,
        epoch,
        CommitteeConfig(config),
    )
    for shard_offset in range(epoch_committee_count):
        shard = Shard((epoch_start_shard + shard_offset) % config.SHARD_COUNT)
        crosslink_committee = get_crosslink_committee(
            state,
            epoch,
            shard,
            CommitteeConfig(config),
        )
        _, attesting_indices = get_winning_crosslink_and_attesting_indices(
            state=state,
            epoch=epoch,
            shard=shard,
            config=config,
        )
        total_attesting_balance = get_total_balance(
            state,
            attesting_indices,
        )
        total_committee_balance = get_total_balance(
            state,
            crosslink_committee,
        )
        for index in crosslink_committee:
            base_reward = get_base_reward(state, index, config)
            if index in attesting_indices:
                rewards = update_tuple_item_with_fn(
                    rewards,
                    index,
                    lambda balance, delta: balance + delta,
                    base_reward * total_attesting_balance // total_committee_balance
                )
            else:
                penalties = update_tuple_item_with_fn(
                    penalties,
                    index,
                    lambda balance, delta: balance + delta,
                    base_reward,
                )
    return tuple(
        Gwei(reward) for reward in rewards
    ), tuple(
        Gwei(penalty) for penalty in penalties
    )


def process_rewards_and_penalties(state: BeaconState, config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    if current_epoch == config.GENESIS_EPOCH:
        return state

    rewards_for_attestations, penalties_for_attestations = get_attestation_deltas(state, config)
    rewards_for_crosslinks, penalties_for_crosslinks = get_crosslink_deltas(state, config)

    for index in range(len(state.validators)):
        index = ValidatorIndex(index)
        state = increase_balance(state, index, Gwei(
            rewards_for_attestations[index] + rewards_for_crosslinks[index]
        ))
        state = decrease_balance(state, index, Gwei(
            penalties_for_attestations[index] + penalties_for_crosslinks[index]
        ))

    return state


@curry
def _process_activation_eligibility_or_ejections(state: BeaconState,
                                                 validator: Validator,
                                                 config: Eth2Config) -> Validator:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    if (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH and
        validator.effective_balance >= config.MAX_EFFECTIVE_BALANCE
    ):
        validator = validator.copy(
            activation_eligibility_epoch=current_epoch,
        )

    if (
        validator.is_active(current_epoch) and
        validator.effective_balance <= config.EJECTION_BALANCE
    ):
        validator = initiate_exit_for_validator(validator, state, config)

    return validator


@curry
def _update_validator_activation_epoch(state: BeaconState,
                                       config: Eth2Config,
                                       validator: Validator) -> Validator:
    if validator.activation_epoch == FAR_FUTURE_EPOCH:
        return validator.copy(
            activation_epoch=get_delayed_activation_exit_epoch(
                state.current_epoch(config.SLOTS_PER_EPOCH),
                config.ACTIVATION_EXIT_DELAY,
            )
        )
    else:
        return validator


def process_registry_updates(state: BeaconState, config: Eth2Config) -> BeaconState:
    new_validators = tuple(
        _process_activation_eligibility_or_ejections(state, validator, config)
        for validator in state.validators
    )

    delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(
        state.finalized_epoch,
        config.ACTIVATION_EXIT_DELAY,
    )
    activation_queue = sorted([
        index for index, validator in enumerate(new_validators) if
        validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH and
        validator.activation_epoch >= delayed_activation_exit_epoch
    ], key=lambda index: new_validators[index].activation_eligibility_epoch)

    for index in activation_queue[:get_churn_limit(state, config)]:
        new_validators = update_tuple_item_with_fn(
            new_validators,
            index,
            _update_validator_activation_epoch(state, config),
        )

    return state.copy(
        validators=new_validators,
    )


def _determine_slashing_penalty(total_penalties: Gwei,
                                total_balance: Gwei,
                                balance: Gwei,
                                min_slashing_penalty_quotient: int) -> Gwei:
    collective_penalty = min(total_penalties * 3, total_balance) // total_balance
    return Gwei(
        max(
            balance * collective_penalty,
            balance // min_slashing_penalty_quotient
        )
    )


def process_slashings(state: BeaconState, config: Eth2Config) -> BeaconState:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    total_balance = get_total_active_balance(state, config)

    start_index = (current_epoch + 1) % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    total_at_start = state.slashed_balances[start_index]

    end_index = current_epoch % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    total_at_end = state.slashed_balances[end_index]

    total_penalties = total_at_end - total_at_start

    slashing_period = config.EPOCHS_PER_SLASHED_BALANCES_VECTOR // 2
    for index, validator in enumerate(state.validators):
        index = ValidatorIndex(index)
        if validator.slashed and current_epoch == validator.withdrawable_epoch - slashing_period:
            penalty = _determine_slashing_penalty(
                total_penalties,
                total_balance,
                validator.effective_balance,
                config.MIN_SLASHING_PENALTY_QUOTIENT,
            )
            state = decrease_balance(state, index, penalty)
    return state


def _determine_next_eth1_votes(state: BeaconState, config: Eth2Config) -> Tuple[Eth1Data, ...]:
    if (state.slot + 1) % config.SLOTS_PER_ETH1_VOTING_PERIOD == 0:
        return tuple()
    else:
        return state.eth1_data_votes


def _update_effective_balances(state: BeaconState, config: Eth2Config) -> Tuple[Validator, ...]:
    half_increment = config.EFFECTIVE_BALANCE_INCREMENT // 2
    new_validators = state.validators
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        if balance < validator.effective_balance or (
            validator.effective_balance + 3 * half_increment < balance
        ):
            new_effective_balance = min(
                balance - balance % config.EFFECTIVE_BALANCE_INCREMENT,
                config.MAX_EFFECTIVE_BALANCE,
            )
            new_validators = update_tuple_item_with_fn(
                new_validators,
                index,
                lambda v, new_balance: v.copy(
                    effective_balance=new_balance,
                ),
                new_effective_balance,
            )
    return new_validators


def _compute_next_start_shard(state: BeaconState, config: Eth2Config) -> Shard:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    return (state.start_shard + get_shard_delta(
        state,
        current_epoch,
        CommitteeConfig(config),
    )) % config.SHARD_COUNT


def _compute_next_active_index_roots(state: BeaconState, config: Eth2Config) -> Tuple[Hash32, ...]:
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    index_root_position = (
        next_epoch + config.ACTIVATION_EXIT_DELAY
    ) % config.EPOCHS_PER_HISTORICAL_VECTOR
    validator_indices_for_new_active_index_root = get_active_validator_indices(
        state.validators,
        Epoch(next_epoch + config.ACTIVATION_EXIT_DELAY),
    )
    new_active_index_root = ssz.hash_tree_root(
        validator_indices_for_new_active_index_root,
        ssz.sedes.List(ssz.uint64),
    )
    return update_tuple_item(
        state.active_index_roots,
        index_root_position,
        new_active_index_root,
    )


def _compute_next_slashed_balances(state: BeaconState, config: Eth2Config) -> Tuple[Gwei, ...]:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    return update_tuple_item(
        state.slashed_balances,
        next_epoch % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR,
        state.slashed_balances[
            current_epoch % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR
        ],
    )


def _compute_next_randao_mixes(state: BeaconState, config: Eth2Config) -> Tuple[Hash32, ...]:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    return update_tuple_item(
        state.randao_mixes,
        next_epoch % config.EPOCHS_PER_HISTORICAL_VECTOR,
        get_randao_mix(
            state,
            current_epoch,
            config.SLOTS_PER_EPOCH,
            config.EPOCHS_PER_HISTORICAL_VECTOR,
        ),
    )


def _compute_next_historical_roots(state: BeaconState, config: Eth2Config) -> Tuple[Hash32, ...]:
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    new_historical_roots = state.historical_roots
    if next_epoch % (config.SLOTS_PER_HISTORICAL_ROOT // config.SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(
            block_roots=state.block_roots,
            state_roots=state.state_roots,
        )
        new_historical_roots = state.historical_roots + (historical_batch.root,)
    return new_historical_roots


def process_final_updates(state: BeaconState, config: Eth2Config) -> BeaconState:
    new_eth1_data_votes = _determine_next_eth1_votes(state, config)
    new_validators = _update_effective_balances(state, config)
    new_start_shard = _compute_next_start_shard(state, config)
    new_active_index_roots = _compute_next_active_index_roots(state, config)
    new_slashed_balances = _compute_next_slashed_balances(state, config)
    new_randao_mixes = _compute_next_randao_mixes(state, config)
    new_historical_roots = _compute_next_historical_roots(state, config)

    return state.copy(
        eth1_data_votes=new_eth1_data_votes,
        validators=new_validators,
        start_shard=new_start_shard,
        active_index_roots=new_active_index_roots,
        slashed_balances=new_slashed_balances,
        randao_mixes=new_randao_mixes,
        historical_roots=new_historical_roots,
        previous_epoch_attestations=state.current_epoch_attestations,
        current_epoch_attestations=tuple(),
    )


def process_epoch(state: BeaconState, config: Eth2Config) -> BeaconState:
    state = process_justification_and_finalization(state, config)
    state = process_crosslinks(state, config)
    state = process_rewards_and_penalties(state, config)
    state = process_registry_updates(state, config)
    state = process_slashings(state, config)
    state = process_final_updates(state, config)

    return state
