from typing import (
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
    to_set,
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
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.pending_attestation_records import (
    PendingAttestationRecord,
)
if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


@to_tuple
def get_previous_epoch_boundary_attestations(
        state: 'BeaconState',
        slots_per_epoch: int,
        genesis_epoch: Epoch,
        latest_block_roots_length: int) -> Iterable[PendingAttestationRecord]:
    beacon_block_root = get_block_root(
        state,
        get_epoch_start_slot(
            state.previous_epoch(slots_per_epoch, genesis_epoch),
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
        genesis_epoch: Epoch,
        slots_per_historical_root: int) -> Iterable[PendingAttestationRecord]:
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
        attestations: Sequence[PendingAttestationRecord],
        latest_crosslink: CrosslinkRecord,
        shard: Shard) -> Iterable[PendingAttestationRecord]:
    for attestation in attestations:
        is_latest_crosslink_matched = attestation.data.previous_crosslink == latest_crosslink
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

    def get_attestations_for(root: Hash32) -> Sequence[PendingAttestationRecord]:
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
@to_set
def get_epoch_boundary_attester_indices(
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        epoch: Epoch,
        root: Hash32,
        committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    for a in attestations:
        if a.data.source_epoch == epoch and a.data.target_root == root:
            yield from get_attestation_participants(
                state,
                a.data,
                a.aggregation_bitfield,
                committee_config,
            )


def get_epoch_boundary_attesting_balances(
        current_epoch: Epoch,
        previous_epoch: Epoch,
        state: 'BeaconState',
        config: Eth2Config) -> Tuple[Gwei, Gwei]:

    previous_epoch_boundary_root = get_block_root(
        state,
        get_epoch_start_slot(previous_epoch, config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    previous_epoch_boundary_attester_indices = get_epoch_boundary_attester_indices(
        state,
        state.current_epoch_attestations + state.previous_epoch_attestations,
        state.previous_justified_epoch,
        previous_epoch_boundary_root,
        CommitteeConfig(config),
    )

    previous_epoch_boundary_attesting_balance = get_total_balance(
        state.validator_balances,
        previous_epoch_boundary_attester_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )

    current_epoch_boundary_root = get_block_root(
        state,
        get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    current_epoch_boundary_attester_indices = get_epoch_boundary_attester_indices(
        state,
        state.current_epoch_attestations,
        state.current_justified_epoch,
        current_epoch_boundary_root,
        CommitteeConfig(config),
    )

    current_epoch_boundary_attesting_balance = get_total_balance(
        state.validator_balances,
        current_epoch_boundary_attester_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )
    return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance


def get_total_balance_from_effective_balances(
        effective_balances: Dict[ValidatorIndex, Gwei],
        validator_indices: Set[ValidatorIndex]) -> Gwei:
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
        attestations: Sequence[PendingAttestationRecord],
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
        attestations: Sequence[PendingAttestationRecord],
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
                attestation.slot_included < inclusion_infos[index].inclusion_slot
            )
            if should_update_inclusion_data:
                inclusion_infos[index] = InclusionInfo(
                    attestation.slot_included,
                    attestation.data.slot
                )
    return inclusion_infos
