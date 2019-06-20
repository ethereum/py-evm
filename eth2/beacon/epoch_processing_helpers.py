from typing import (  # noqa: F401
    Dict,
    Iterable,
    Sequence,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    curry,
)

from eth2._utils.bitfield import (
    Bitfield,
    has_voted
)
from eth2._utils.numeric import integer_squareroot
from eth2._utils.tuple import update_tuple_item_with_fn
from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committee,
)
from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.exceptions import (
    InvalidEpochError,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_block_root_at_slot,
    get_total_balance,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    ValidatorIndex,
)

from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.pending_attestations import (
    PendingAttestation,
)
if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401


def get_churn_limit(state: 'BeaconState',
                    slots_per_epoch: int,
                    min_per_epoch_churn_limit: int,
                    churn_limit_quotient: int) -> int:
    current_epoch = state.current_epoch(slots_per_epoch)
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        current_epoch,
    )
    return max(
        min_per_epoch_churn_limit,
        len(active_validator_indices) // churn_limit_quotient
    )


def increase_balance(state: 'BeaconState', index: ValidatorIndex, delta: Gwei) -> 'BeaconState':
    return state.copy(
        validator_registry=update_tuple_item_with_fn(
            state.validator_registry,
            index,
            sum,
            delta,
        ),
    )


def decrease_balance(state: 'BeaconState', index: ValidatorIndex, delta: Gwei) -> 'BeaconState':
    return state.copy(
        validator_registry=update_tuple_item_with_fn(
            state.validator_registry,
            index,
            lambda balance: 0 if delta > balance else balance - delta
        ),
    )


# @to_tuple
# def get_previous_epoch_boundary_attestations(
#         state: 'BeaconState',
#         slots_per_epoch: int,
#         latest_block_roots_length: int) -> Iterable[PendingAttestation]:
#     if not state.previous_epoch_attestations:
#         return tuple()

#     beacon_block_root = get_block_root(
#         state,
#         get_epoch_start_slot(
#             state.previous_epoch(slots_per_epoch),
#             slots_per_epoch,
#         ),
#         latest_block_roots_length,
#     )
#     for attestation in state.previous_epoch_attestations:
#         if attestation.data.beacon_block_root == beacon_block_root:
#             yield attestation


# @to_tuple
# def get_previous_epoch_matching_head_attestations(
#         state: 'BeaconState',
#         slots_per_epoch: int,
#         slots_per_historical_root: int) -> Iterable[PendingAttestation]:
#     for attestation in state.previous_epoch_attestations:
#         beacon_block_root = get_block_root(
#             state,
#             attestation.data.slot,
#             slots_per_historical_root,
#         )
#         if attestation.data.beacon_block_root == beacon_block_root:
#             yield attestation


# @to_tuple
# def _filter_attestations_by_latest_crosslinks_and_shard(
#         attestations: Sequence[PendingAttestation],
#         latest_crosslink: Crosslink,
#         shard: Shard) -> Iterable[PendingAttestation]:
#     for attestation in attestations:
#         is_latest_crosslink_matched = attestation.data.previous_crosslink == latest_crosslink
#         # NOTE: v0.5.1 doesn't check is_shard_matched but it's fixed in v0.6.0
#         # We implemented ahead here.
#         is_shard_matched = attestation.data.shard == shard
#         if is_latest_crosslink_matched and is_shard_matched:
#             yield attestation


@to_tuple
def get_attesting_indices(state: 'BeaconState',
                          attestation_data: 'AttestationData',
                          bitfield: Bitfield) -> Iterable[ValidatorIndex]:
    """
    Return the sorted attesting indices corresponding to ``attestation_data`` and ``bitfield``.
    """
    committee = get_crosslink_committee(
        state,
        attestation_data.target_epoch,
        attestation_data.crosslink.shard,
    )
    return sorted(index for i, index in enumerate(committee) if has_voted(bitfield, i))


def _get_matching_source_attestations(state: 'BeaconState',
                                      epoch: Epoch,
                                      config: Eth2Config) -> Tuple[PendingAttestation, ...]:
    if epoch == state.current_epoch(config.SLOTS_PER_EPOCH):
        return state.current_epoch_attestations
    elif epoch == state.previous_epoch(config.SLOTS_PER_EPOCH):
        return state.previous_epoch_attestations
    else:
        raise InvalidEpochError


@to_tuple
def _get_matching_target_attestations(state: 'BeaconState',
                                      epoch: Epoch) -> Iterable[PendingAttestation]:
    target_root = get_block_root(state, epoch)

    for a in _get_matching_source_attestations(state, epoch):
        if a.data.target_root == target_root:
            yield a


@to_tuple
def _get_matching_head_attestations(state: 'BeaconState',
                                    epoch: Epoch,
                                    config: Eth2Config) -> Iterable[PendingAttestation]:
    for a in _get_matching_source_attestations(state, epoch):
        beacon_block_root = get_block_root_at_slot(
            state,
            get_attestation_data_slot(
                state,
                a.data,
                config,
            ),
            config.SLOTS_PER_HISTORICAL_ROOT,
        )
        if a.data.beacon_block_root == beacon_block_root:
            yield a


@to_tuple
def _get_unslashed_attesting_indices(
        state: 'BeaconState',
        attestations: Sequence[PendingAttestation]) -> Iterable[ValidatorIndex]:
    output = set()
    for a in attestations:
        output = output.union(get_attesting_indices(state, a.data, a.aggregation_bitfield))
    return sorted(
        filter(
            lambda index: not state.validator_registry[index].slashed,
            tuple(output),
        )
    )


def _get_attesting_balance(state: 'BeaconState',
                           attestations: Sequence[PendingAttestation],
                           config: Eth2Config) -> Gwei:
    return get_total_balance(
        state,
        _get_unslashed_attesting_indices(state, attestations, config)
    )


@curry
def _state_contains_crosslink_or_parent(state: 'BeaconState', shard: Shard, c: Crosslink) -> bool:
    current_crosslink = state.current_crosslinks[shard]
    return current_crosslink.root in (c.parent_root, c.root)


@curry
def _score_winning_crosslink(state: 'BeaconState',
                             attestations: Sequence[PendingAttestation],
                             config: Eth2Config,
                             c: Crosslink) -> int:
    balance = _get_attesting_balance(
        state,
        tuple(
            a for a in attestations if a.data.crosslink == c
        ),
        config,
    )
    return (balance, c.data_root)


def get_winning_crosslink_and_attesting_indices(
        *,
        state: 'BeaconState',
        epoch: Epoch,
        shard: Shard,
        effective_balances: Dict[ValidatorIndex, Gwei],
        committee_config: CommitteeConfig) -> Tuple[Hash32, Tuple[ValidatorIndex, ...]]:
    matching_attestations = _get_matching_source_attestations(
        state,
        epoch,
        committee_config,
    )
    candidate_attestations = tuple(
        a for a in matching_attestations
        if a.data.crosslink.shard == shard
    )
    all_crosslinks = map(lambda a: a.data.crosslink, candidate_attestations)
    candidate_crosslinks = filter(
        _state_contains_crosslink_or_parent(state, shard),
        all_crosslinks,
    )

    winning_crosslink = max(
        candidate_crosslinks,
        key=_score_winning_crosslink(
            state,
            candidate_attestations,
            committee_config,
        ),
        default=Crosslink(),
    )

    winning_attestations = tuple(
        a for a in candidate_attestations if a.data.crosslink == winning_crosslink
    )

    return (
        winning_crosslink,
        _get_unslashed_attesting_indices(
            state,
            winning_attestations,
            committee_config,
        )
    )


# def _get_epoch_boundary_attesting_indices(state: 'BeaconState',
#                                           attestations: Sequence[PendingAttestation],
#                                           epoch: Epoch,
#                                           config: Eth2Config) -> Tuple[ValidatorIndex, ...]:
#     target_root = get_block_root(
#         state,
#         get_epoch_start_slot(
#             epoch,
#             config.SLOTS_PER_EPOCH
#         ),
#         config.SLOTS_PER_HISTORICAL_ROOT,
#     )
#     relevant_attestations = (
#         a for a in attestations
#         if a.data.target_root == target_root
#     )
#     return get_attesting_indices(
#         state,
#         relevant_attestations,
#         config,
#     )


# def get_epoch_boundary_attesting_balance(state: 'BeaconState',
#                                          attestations: Sequence[PendingAttestation],
#                                          epoch: Epoch,
#                                          config: Eth2Config) -> Gwei:
#     attesting_indices = _get_epoch_boundary_attesting_indices(state, attestations, epoch, config)
#     return get_total_balance(
#         state.validator_balances,
#         attesting_indices,
#         config.MAX_EFFECTIVE_BALANCE,
#     )


# def get_total_balance_from_effective_balances(
#         effective_balances: Dict[ValidatorIndex, Gwei],
#         validator_indices: Sequence[ValidatorIndex]) -> Gwei:
#     return Gwei(
#         sum(
#             effective_balances[index]
#             for index in validator_indices
#         )
#     )


# def get_attesting_balance_from_attestations(
#         *,
#         state: 'BeaconState',
#         effective_balances: Dict[ValidatorIndex, Gwei],
#         attestations: Sequence[PendingAttestation],
#         committee_config: CommitteeConfig) -> Gwei:
#     return get_total_balance_from_effective_balances(
#         effective_balances,
#         get_attester_indices_from_attestations(
#             state=state,
#             attestations=attestations,
#             committee_config=committee_config,
#         ),
#     )


def _get_total_active_balance(state: 'BeaconState', validator_index: ValidatorIndex,
                              slots_per_epoch: int) -> Gwei:
    current_epoch = state.current_epoch(slots_per_epoch)
    active_validator_indices = get_active_validator_indices(state, current_epoch)
    return get_total_balance(state, active_validator_indices)


# ?
def get_base_reward(state: 'BeaconState',
                    index: ValidatorIndex,
                    base_reward_factor: int,
                    base_rewards_per_epoch: int,
                    slots_per_epoch: int) -> Gwei:
    total_balance = _get_total_active_balance(state, index, slots_per_epoch)
    effective_balance = state.validator_registry[index].effective_balance
    return (
        effective_balance * base_reward_factor //
        integer_squareroot(total_balance) // base_rewards_per_epoch
    )


# ?
def get_inactivity_penalty(
        *,
        base_reward: Gwei,
        effective_balance: Gwei,
        epochs_since_finality: int,
        inactivity_penalty_quotient: int) -> Gwei:
    return Gwei(
        base_reward +
        effective_balance * epochs_since_finality // inactivity_penalty_quotient // 2
    )


# def get_inclusion_infos(
#         *,
#         state: 'BeaconState',
#         attestations: Sequence[PendingAttestation],
#         committee_config: CommitteeConfig) -> Dict[ValidatorIndex, InclusionInfo]:  # noqa: E501
#     """
#     Return two maps. One with ``ValidatorIndex`` -> ``inclusion_slot`` and the other with
#     ``ValidatorIndex`` -> ``inclusion_distance``.

#     ``attestation.inclusion_slot`` is the slot during which the pending attestation is included.
#     ``inclusion_distance = attestation.inclusion_slot - attestation.data.slot``
#     """
#     inclusion_infos: Dict[ValidatorIndex, InclusionInfo] = {}
#     for attestation in attestations:
#         participant_indices = get_attestation_participants(
#             state,
#             attestation.data,
#             attestation.aggregation_bitfield,
#             committee_config,
#         )
#         for index in participant_indices:
#             should_update_inclusion_data = (
#                 index not in inclusion_infos or
#                 attestation.inclusion_slot < inclusion_infos[index].inclusion_slot
#             )
#             if should_update_inclusion_data:
#                 inclusion_infos[index] = InclusionInfo(
#                     attestation.inclusion_slot,
#                     attestation.data.slot
#                 )
#     return inclusion_infos
