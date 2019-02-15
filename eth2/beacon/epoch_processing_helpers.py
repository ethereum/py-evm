import math
from typing import (
    Dict,
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    to_set,
    to_tuple,
)


from eth2.beacon.committee_helpers import (
    get_attestation_participants,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.exceptions import (
    NoWinningRootError,
)
from eth2.beacon.helpers import (
    get_block_root,
    get_epoch_start_slot,
    get_effective_balance,
    get_total_balance,
    slot_to_epoch,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    Slot,
    ValidatorIndex,
)

from eth2.beacon.types.pending_attestation_records import (
    PendingAttestationRecord,
)
if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401
    from eth2.beacon.state_machines.configs import BeaconConfig  # noqa: F401


@to_tuple
def get_current_epoch_attestations(
        state: 'BeaconState',
        slots_per_epoch: int) -> Iterable[PendingAttestationRecord]:
    current_epoch = state.current_epoch(slots_per_epoch)
    for attestation in state.latest_attestations:
        if current_epoch == slot_to_epoch(attestation.data.slot, slots_per_epoch):
            yield attestation


@to_tuple
def get_previous_epoch_attestations(
        state: 'BeaconState',
        slots_per_epoch: int,
        genesis_epoch: Epoch) -> Iterable[PendingAttestationRecord]:
    previous_epoch = state.previous_epoch(slots_per_epoch, genesis_epoch)
    for attestation in state.latest_attestations:
        if previous_epoch == slot_to_epoch(attestation.data.slot, slots_per_epoch):
            yield attestation


@to_tuple
def get_previous_epoch_justified_attestations(
        state: 'BeaconState',
        epoch_length: int,
        genesis_epoch: EpochNumber) -> Iterable[PendingAttestationRecord]:
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        epoch_length,
        genesis_epoch,
    )
    current_epoch_attestations = get_current_epoch_attestations(state, epoch_length)
    for attestation in (previous_epoch_attestations + current_epoch_attestations):
        if attestation.data.justified_epoch == state.previous_justified_epoch:
            yield attestation


@to_tuple
def get_previous_epoch_head_attestations(
        state: 'BeaconState',
        epoch_length: int,
        genesis_epoch: EpochNumber,
        latest_block_roots_length: int) -> Iterable[PendingAttestationRecord]:
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        epoch_length,
        genesis_epoch,
    )
    for attestation in previous_epoch_attestations:
        beacon_block_root = get_block_root(
            state,
            attestation.data.slot,
            latest_block_roots_length,
        )
        if attestation.data.beacon_block_root == beacon_block_root:
            yield attestation


@to_tuple
@to_set
def get_shard_block_root_attester_indices(
        *,
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        shard: Shard,
        shard_block_root: Hash32,
        committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    """
    Loop through ``attestations`` and check if ``shard``/``shard_block_root`` in the attestation
    matches the given ``shard``/``shard_block_root``.
    If the attestation matches, get the index of the participating validators.
    Finally, return the union of the indices.
    """
    for a in attestations:
        if a.data.shard == shard and a.data.shard_block_root == shard_block_root:
            yield from get_attestation_participants(
                state,
                a.data,
                a.aggregation_bitfield,
                committee_config,
            )


def get_shard_block_root_total_attesting_balance(
        *,
        state: 'BeaconState',
        shard: Shard,
        shard_block_root: Hash32,
        attestations: Sequence[PendingAttestationRecord],
        max_deposit_amount: Gwei,
        committee_config: CommitteeConfig) -> Gwei:
    validator_indices = get_shard_block_root_attester_indices(
        state=state,
        attestations=attestations,
        shard=shard,
        shard_block_root=shard_block_root,
        committee_config=committee_config,
    )
    return get_total_balance(
        state.validator_balances,
        validator_indices,
        max_deposit_amount,
    )


def get_winning_root(
        *,
        state: 'BeaconState',
        shard: Shard,
        attestations: Sequence[PendingAttestationRecord],
        max_deposit_amount: Gwei,
        committee_config: CommitteeConfig) -> Tuple[Hash32, Gwei]:
    winning_root = None
    winning_root_balance: Gwei = Gwei(0)
    shard_block_roots = set(
        [
            a.data.shard_block_root for a in attestations
            if a.data.shard == shard
        ]
    )
    for shard_block_root in shard_block_roots:
        total_attesting_balance = get_shard_block_root_total_attesting_balance(
            state=state,
            shard=shard,
            shard_block_root=shard_block_root,
            attestations=attestations,
            max_deposit_amount=max_deposit_amount,
            committee_config=committee_config,
        )
        if total_attesting_balance > winning_root_balance:
            winning_root = shard_block_root
            winning_root_balance = total_attesting_balance
        elif total_attesting_balance == winning_root_balance and winning_root_balance > 0:
            if shard_block_root < winning_root:
                winning_root = shard_block_root

    if winning_root is None:
        raise NoWinningRootError
    return (winning_root, winning_root_balance)


@to_tuple
@to_set
def get_epoch_boundary_attester_indices(
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        epoch: Epoch,
        root: Hash32,
        committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    for a in attestations:
        if a.data.justified_epoch == epoch and a.data.epoch_boundary_root == root:
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
        config: 'BeaconConfig') -> Tuple[Gwei, Gwei]:

    current_epoch_attestations = get_current_epoch_attestations(state, config.SLOTS_PER_EPOCH)
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        config.SLOTS_PER_EPOCH,
        config.GENESIS_EPOCH,
    )

    previous_epoch_boundary_root = get_block_root(
        state,
        get_epoch_start_slot(previous_epoch, config.SLOTS_PER_EPOCH),
        config.LATEST_BLOCK_ROOTS_LENGTH,
    )

    previous_epoch_boundary_attester_indices = get_epoch_boundary_attester_indices(
        state,
        current_epoch_attestations + previous_epoch_attestations,
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
        config.LATEST_BLOCK_ROOTS_LENGTH,
    )

    current_epoch_boundary_attester_indices = get_epoch_boundary_attester_indices(
        state,
        current_epoch_attestations,
        state.justified_epoch,
        current_epoch_boundary_root,
        CommitteeConfig(config),
    )

    current_epoch_boundary_attesting_balance = get_total_balance(
        state.validator_balances,
        current_epoch_boundary_attester_indices,
        config.MAX_DEPOSIT_AMOUNT,
    )
    return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance
def get_base_reward(
        *,
        state: 'BeaconState',
        index: ValidatorIndex,
        previous_total_balance: Gwei,
        base_reward_quotient: int,
        max_deposit_amount: Gwei) -> Gwei:
    _base_reward_quotient = int(math.sqrt(previous_total_balance)) // base_reward_quotient
    return Gwei(
        get_effective_balance(
            state.validator_balances,
            index,
            max_deposit_amount,
        ) // _base_reward_quotient // 5
    )


def get_inclusion_info_map(
        *,
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        genesis_epoch: EpochNumber,
        epoch_length: int,
        target_committee_size: int,
        shard_count: int) -> Tuple[Dict[ValidatorIndex, Slot], Dict[ValidatorIndex, int]]:
    inclusion_slot_map: Dict[ValidatorIndex, Slot] = {}
    inclusion_distance_map: Dict[ValidatorIndex, int] = {}
    for attestation in attestations:
        participant_indices = get_attestation_participants(
            state,
            attestation.data,
            attestation.aggregation_bitfield,
            genesis_epoch,
            epoch_length,
            target_committee_size,
            shard_count,
        )
        for index in participant_indices:
            inclusion_slot = inclusion_slot_map.get(index)
            if inclusion_slot is None:
                inclusion_slot_map[index] = attestation.slot_included
                inclusion_distance_map[index] = attestation.slot_included - attestation.data.slot
            elif attestation.slot_included < inclusion_slot:
                inclusion_slot_map[index] = attestation.slot_included
                inclusion_distance_map[index] = attestation.slot_included - attestation.data.slot
    return (inclusion_slot_map, inclusion_distance_map)
