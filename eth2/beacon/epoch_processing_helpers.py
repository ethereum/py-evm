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

from eth2.beacon.committee_helpers import (
    get_attestation_participants,
    get_attester_indices_from_attesttion,
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
    ValidatorIndex,
)

from eth2.beacon.datastructures.inclusion_info import InclusionInfo
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
def get_previous_epoch_head_attestations(
        state: 'BeaconState',
        slots_per_epoch: int,
        genesis_epoch: Epoch,
        latest_block_roots_length: int) -> Iterable[PendingAttestationRecord]:
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        slots_per_epoch,
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


def get_winning_root(
        *,
        state: 'BeaconState',
        shard: Shard,
        attestations: Sequence[PendingAttestationRecord],
        max_deposit_amount: Gwei,
        committee_config: CommitteeConfig) -> Tuple[Hash32, Gwei]:
    winning_root = None
    winning_root_balance: Gwei = Gwei(0)
    crosslink_data_roots = set(
        [
            a.data.crosslink_data_root for a in attestations
            if a.data.shard == shard
        ]
    )
    for crosslink_data_root in crosslink_data_roots:
        attesting_validator_indices = get_attester_indices_from_attesttion(
            state=state,
            attestations=[
                a
                for a in attestations
                if a.data.shard == shard and a.data.crosslink_data_root == crosslink_data_root
            ],
            committee_config=committee_config,
        )
        total_attesting_balance = get_total_balance(
            state.validator_balances,
            attesting_validator_indices,
            max_deposit_amount,
        )
        if total_attesting_balance > winning_root_balance:
            winning_root = crosslink_data_root
            winning_root_balance = total_attesting_balance
        elif total_attesting_balance == winning_root_balance and winning_root_balance > 0:
            if crosslink_data_root < winning_root:
                winning_root = crosslink_data_root

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


def get_total_balance_from_effective_balances(
        effective_balances: Dict[ValidatorIndex, Gwei],
        validator_indices: Set[ValidatorIndex]) -> Gwei:
    return Gwei(
        sum(
            effective_balances[index]
            for index in validator_indices
        )
    )


def get_base_reward(
        *,
        state: 'BeaconState',
        index: ValidatorIndex,
        base_reward_quotient: int,
        max_deposit_amount: Gwei) -> Gwei:
    return Gwei(
        get_effective_balance(
            state.validator_balances,
            index,
            max_deposit_amount,
        ) // base_reward_quotient // 5
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
