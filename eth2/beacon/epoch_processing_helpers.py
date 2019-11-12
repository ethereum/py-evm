from typing import Iterable, Sequence, Set, Tuple

from eth_utils import to_tuple

from eth2._utils.bitfield import Bitfield, has_voted
from eth2._utils.numeric import integer_squareroot
from eth2._utils.tuple import update_tuple_item_with_fn
from eth2.beacon.committee_helpers import get_beacon_committee
from eth2.beacon.constants import BASE_REWARDS_PER_EPOCH
from eth2.beacon.exceptions import InvalidEpochError
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_block_root_at_slot,
    get_total_balance,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Epoch, Gwei, ValidatorIndex
from eth2.configs import CommitteeConfig, Eth2Config


def increase_balance(
    state: BeaconState, index: ValidatorIndex, delta: Gwei
) -> BeaconState:
    return state.copy(
        balances=update_tuple_item_with_fn(
            state.balances, index, lambda balance, *_: Gwei(balance + delta)
        )
    )


def decrease_balance(
    state: BeaconState, index: ValidatorIndex, delta: Gwei
) -> BeaconState:
    return state.copy(
        balances=update_tuple_item_with_fn(
            state.balances,
            index,
            lambda balance, *_: Gwei(0) if delta > balance else Gwei(balance - delta),
        )
    )


def get_attesting_indices(
    state: BeaconState,
    attestation_data: AttestationData,
    bitfield: Bitfield,
    config: CommitteeConfig,
) -> Set[ValidatorIndex]:
    """
    Return the sorted attesting indices corresponding to ``attestation_data`` and ``bitfield``.
    """
    committee = get_beacon_committee(
        state, attestation_data.slot, attestation_data.index, config
    )
    return set(index for i, index in enumerate(committee) if has_voted(bitfield, i))


def get_indexed_attestation(
    state: BeaconState, attestation: Attestation, config: CommitteeConfig
) -> IndexedAttestation:
    attesting_indices = get_attesting_indices(
        state, attestation.data, attestation.aggregation_bits, config
    )

    return IndexedAttestation(
        attesting_indices=sorted(attesting_indices),
        data=attestation.data,
        signature=attestation.signature,
    )


def compute_activation_exit_epoch(epoch: Epoch, max_seed_lookahead: int) -> Epoch:
    """
    An entry or exit triggered in the ``epoch`` given by the input takes effect at
    the epoch given by the output.
    """
    return Epoch(epoch + 1 + max_seed_lookahead)


def get_validator_churn_limit(state: BeaconState, config: Eth2Config) -> int:
    slots_per_epoch = config.SLOTS_PER_EPOCH
    min_per_epoch_churn_limit = config.MIN_PER_EPOCH_CHURN_LIMIT
    churn_limit_quotient = config.CHURN_LIMIT_QUOTIENT

    current_epoch = state.current_epoch(slots_per_epoch)
    active_validator_indices = get_active_validator_indices(
        state.validators, current_epoch
    )
    return max(
        min_per_epoch_churn_limit, len(active_validator_indices) // churn_limit_quotient
    )


def get_total_active_balance(state: BeaconState, config: Eth2Config) -> Gwei:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    active_validator_indices = get_active_validator_indices(
        state.validators, current_epoch
    )
    return get_total_balance(state, set(active_validator_indices))


def get_matching_source_attestations(
    state: BeaconState, epoch: Epoch, config: Eth2Config
) -> Tuple[PendingAttestation, ...]:
    if epoch == state.current_epoch(config.SLOTS_PER_EPOCH):
        return state.current_epoch_attestations
    elif epoch == state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH):
        return state.previous_epoch_attestations
    else:
        raise InvalidEpochError


@to_tuple
def get_matching_target_attestations(
    state: BeaconState, epoch: Epoch, config: Eth2Config
) -> Iterable[PendingAttestation]:
    target_root = get_block_root(
        state, epoch, config.SLOTS_PER_EPOCH, config.SLOTS_PER_HISTORICAL_ROOT
    )

    for a in get_matching_source_attestations(state, epoch, config):
        if a.data.target.root == target_root:
            yield a


@to_tuple
def get_matching_head_attestations(
    state: BeaconState, epoch: Epoch, config: Eth2Config
) -> Iterable[PendingAttestation]:
    for a in get_matching_source_attestations(state, epoch, config):
        beacon_block_root = get_block_root_at_slot(
            state, a.data.slot, config.SLOTS_PER_HISTORICAL_ROOT
        )
        if a.data.beacon_block_root == beacon_block_root:
            yield a


def get_unslashed_attesting_indices(
    state: BeaconState,
    attestations: Sequence[PendingAttestation],
    config: CommitteeConfig,
) -> Set[ValidatorIndex]:
    output: Set[ValidatorIndex] = set()
    for a in attestations:
        output = output.union(
            get_attesting_indices(state, a.data, a.aggregation_bits, config)
        )
    return set(filter(lambda index: not state.validators[index].slashed, output))


def get_attesting_balance(
    state: BeaconState, attestations: Sequence[PendingAttestation], config: Eth2Config
) -> Gwei:
    return get_total_balance(
        state,
        get_unslashed_attesting_indices(state, attestations, CommitteeConfig(config)),
    )


def get_base_reward(
    state: BeaconState, index: ValidatorIndex, config: Eth2Config
) -> Gwei:
    total_balance = get_total_active_balance(state, config)
    effective_balance = state.validators[index].effective_balance
    return Gwei(
        effective_balance
        * config.BASE_REWARD_FACTOR
        // integer_squareroot(total_balance)
        // BASE_REWARDS_PER_EPOCH
    )
