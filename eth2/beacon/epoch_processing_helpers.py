from typing import (
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
    get_epoch_start_slot,
    slot_to_epoch,
    get_block_root,
    get_total_balance,
)
from eth2.beacon.typing import (
    EpochNumber,
    Gwei,
    ShardNumber,
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
        epoch_length: int) -> Iterable[PendingAttestationRecord]:
    for attestation in state.latest_attestations:
        if state.current_epoch(epoch_length) == slot_to_epoch(attestation.data.slot, epoch_length):
            yield attestation


@to_tuple
def get_previous_epoch_attestations(
        state: 'BeaconState',
        epoch_length: int,
        genesis_epoch: EpochNumber) -> Iterable[PendingAttestationRecord]:
    previous_epoch = state.previous_epoch(epoch_length, genesis_epoch)
    for attestation in state.latest_attestations:
        if previous_epoch == slot_to_epoch(attestation.data.slot, epoch_length):
            yield attestation


@to_tuple
@to_set
def get_attesting_validator_indices(
        *,
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        shard: ShardNumber,
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


def get_total_attesting_balance(
        *,
        state: 'BeaconState',
        shard: ShardNumber,
        shard_block_root: Hash32,
        attestations: Sequence[PendingAttestationRecord],
        max_deposit_amount: Gwei,
        committee_config: CommitteeConfig) -> Gwei:
    validator_indices = get_attesting_validator_indices(
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
        shard: ShardNumber,
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
        total_attesting_balance = get_total_attesting_balance(
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
        epoch: EpochNumber,
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
        current_epoch: EpochNumber,
        previous_epoch: EpochNumber,
        state: 'BeaconState',
        config: 'BeaconConfig') -> Tuple[Gwei, Gwei]:

    current_epoch_attestations = get_current_epoch_attestations(state, config.EPOCH_LENGTH)
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        config.EPOCH_LENGTH,
        config.GENESIS_EPOCH,
    )

    previous_epoch_boundary_root = get_block_root(
        state,
        get_epoch_start_slot(previous_epoch, config.EPOCH_LENGTH),
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
        get_epoch_start_slot(current_epoch, config.EPOCH_LENGTH),
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
