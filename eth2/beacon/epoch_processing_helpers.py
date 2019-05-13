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

from eth.constants import ZERO_HASH32
from eth2._utils.numeric import integer_squareroot
from eth2.beacon.committee_helpers import (
    get_attestation_participants,
    get_attester_indices_from_attestations,
)
from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.helpers import (
    get_block_root,
    get_epoch_start_slot,
    get_effective_balance,
    get_total_balance,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    ValidatorIndex,
)

from eth2.beacon.datastructures.inclusion_info import InclusionInfo
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.pending_attestations import (
    PendingAttestation,
)
if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
    from eth2.beacon.types.validators import Validator  # noqa: F401


@to_tuple
def get_previous_epoch_boundary_attestations(
        state: 'BeaconState',
        slots_per_epoch: int,
        latest_block_roots_length: int) -> Iterable[PendingAttestation]:
    if not state.previous_epoch_attestations:
        return tuple()

    beacon_block_root = get_block_root(
        state,
        get_epoch_start_slot(
            state.previous_epoch(slots_per_epoch),
            slots_per_epoch,
        ),
        latest_block_roots_length,
    )
    for attestation in state.previous_epoch_attestations:
        if attestation.data.beacon_block_root == beacon_block_root:
            yield attestation


@to_tuple
def get_previous_epoch_matching_head_attestations(
        state: 'BeaconState',
        slots_per_epoch: int,
        slots_per_historical_root: int) -> Iterable[PendingAttestation]:
    for attestation in state.previous_epoch_attestations:
        beacon_block_root = get_block_root(
            state,
            attestation.data.slot,
            slots_per_historical_root,
        )
        if attestation.data.beacon_block_root == beacon_block_root:
            yield attestation


@to_tuple
def _filter_attestations_by_latest_crosslinks_and_shard(
        attestations: Sequence[PendingAttestation],
        latest_crosslink: Crosslink,
        shard: Shard) -> Iterable[PendingAttestation]:
    for attestation in attestations:
        is_latest_crosslink_matched = attestation.data.previous_crosslink == latest_crosslink
        # NOTE: v0.5.1 doesn't check is_shard_matched but it's fixed in v0.6.0
        # We implemented ahead here.
        is_shard_matched = attestation.data.shard == shard
        if is_latest_crosslink_matched and is_shard_matched:
            yield attestation


def get_winning_root_and_participants(
        *,
        state: 'BeaconState',
        shard: Shard,
        effective_balances: Dict[ValidatorIndex, Gwei],
        committee_config: CommitteeConfig) -> Tuple[Hash32, Tuple[ValidatorIndex, ...]]:
    valid_attestations = _filter_attestations_by_latest_crosslinks_and_shard(
        state.current_epoch_attestations + state.previous_epoch_attestations,
        state.latest_crosslinks[shard],
        shard,
    )
    all_roots = set([a.data.crosslink_data_root for a in valid_attestations])

    # handle when no attestations for shard available
    if len(all_roots) == 0:
        return (Hash32(ZERO_HASH32), tuple())

    def get_attestations_for(root: Hash32) -> Sequence[PendingAttestation]:
        return [a for a in valid_attestations if a.data.crosslink_data_root == root]

    # Winning crosslink root is the root with the most votes for it, ties broken in favor of
    # lexicographically higher hash
    winning_root: Hash32 = max(
        all_roots,
        key=lambda r: (
            get_attesting_balance_from_attestations(
                state=state,
                effective_balances=effective_balances,
                attestations=get_attestations_for(r),
                committee_config=committee_config,
            ),
            r,
        ),
    )

    return (
        winning_root,
        get_attester_indices_from_attestations(
            state=state,
            attestations=get_attestations_for(winning_root),
            committee_config=committee_config,
        ),
    )


@to_tuple
def get_attesting_indices(state: 'BeaconState',
                          attestations: Sequence[PendingAttestation],
                          config: Eth2Config) -> Iterable[ValidatorIndex]:
    output: Set[ValidatorIndex] = set()
    for a in attestations:
        participants = get_attestation_participants(
            state,
            a.data,
            a.aggregation_bitfield,
            CommitteeConfig(config),
        )
        output = output.union(participants)
    for result in sorted(output):
        yield result


def _get_epoch_boundary_attesting_indices(state: 'BeaconState',
                                          attestations: Sequence[PendingAttestation],
                                          epoch: Epoch,
                                          config: Eth2Config) -> Tuple[ValidatorIndex, ...]:
    target_root = get_block_root(
        state,
        get_epoch_start_slot(
            epoch,
            config.SLOTS_PER_EPOCH
        ),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    relevant_attestations = (
        a for a in attestations
        if a.data.target_root == target_root
    )
    return get_attesting_indices(
        state,
        relevant_attestations,
        config,
    )


def get_epoch_boundary_attesting_balance(state: 'BeaconState',
                                         attestations: Sequence[PendingAttestation],
                                         epoch: Epoch,
                                         config: Eth2Config) -> Gwei:
    attesting_indices = _get_epoch_boundary_attesting_indices(state, attestations, epoch, config)
    return get_total_balance(
        state.validator_balances,
        attesting_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )


def get_total_balance_from_effective_balances(
        effective_balances: Dict[ValidatorIndex, Gwei],
        validator_indices: Sequence[ValidatorIndex]) -> Gwei:
    return Gwei(
        sum(
            effective_balances[index]
            for index in validator_indices
        )
    )


def get_attesting_balance_from_attestations(
        *,
        state: 'BeaconState',
        effective_balances: Dict[ValidatorIndex, Gwei],
        attestations: Sequence[PendingAttestation],
        committee_config: CommitteeConfig) -> Gwei:
    return get_total_balance_from_effective_balances(
        effective_balances,
        get_attester_indices_from_attestations(
            state=state,
            attestations=attestations,
            committee_config=committee_config,
        ),
    )


def get_base_reward(
        *,
        state: 'BeaconState',
        index: ValidatorIndex,
        base_reward_quotient: int,
        previous_total_balance: Gwei,
        max_deposit_amount: Gwei) -> Gwei:
    if previous_total_balance == 0:
        return Gwei(0)
    adjusted_quotient = (
        integer_squareroot(previous_total_balance) // base_reward_quotient
    )
    return Gwei(
        get_effective_balance(
            state.validator_balances,
            index,
            max_deposit_amount,
        ) // adjusted_quotient // 5
    )


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


def get_inclusion_infos(
        *,
        state: 'BeaconState',
        attestations: Sequence[PendingAttestation],
        committee_config: CommitteeConfig) -> Dict[ValidatorIndex, InclusionInfo]:  # noqa: E501
    """
    Return two maps. One with ``ValidatorIndex`` -> ``inclusion_slot`` and the other with
    ``ValidatorIndex`` -> ``inclusion_distance``.

    ``attestation.inclusion_slot`` is the slot during which the pending attestation is included.
    ``inclusion_distance = attestation.inclusion_slot - attestation.data.slot``
    """
    inclusion_infos: Dict[ValidatorIndex, InclusionInfo] = {}
    for attestation in attestations:
        participant_indices = get_attestation_participants(
            state,
            attestation.data,
            attestation.aggregation_bitfield,
            committee_config,
        )
        for index in participant_indices:
            should_update_inclusion_data = (
                index not in inclusion_infos or
                attestation.inclusion_slot < inclusion_infos[index].inclusion_slot
            )
            if should_update_inclusion_data:
                inclusion_infos[index] = InclusionInfo(
                    attestation.inclusion_slot,
                    attestation.data.slot
                )
    return inclusion_infos
