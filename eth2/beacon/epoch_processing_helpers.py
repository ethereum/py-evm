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
from eth2.beacon.exceptions import (
    NoWinningRootError,
)
from eth2.beacon.helpers import (
    get_effective_balance,
    slot_to_epoch,
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
        genesis_epoch: EpochNumber,
        epoch_length: int,
        target_committee_size: int,
        shard_count: int) -> Iterable[ValidatorIndex]:
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
                genesis_epoch,
                epoch_length,
                target_committee_size,
                shard_count,
            )


def get_total_attesting_balance(
        *,
        state: 'BeaconState',
        shard: ShardNumber,
        shard_block_root: Hash32,
        attestations: Sequence[PendingAttestationRecord],
        genesis_epoch: EpochNumber,
        epoch_length: int,
        max_deposit_amount: Gwei,
        target_committee_size: int,
        shard_count: int) -> Gwei:
    return Gwei(
        sum(
            get_effective_balance(state.validator_balances, i, max_deposit_amount)
            for i in get_attesting_validator_indices(
                state=state,
                attestations=attestations,
                shard=shard,
                shard_block_root=shard_block_root,
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length,
                target_committee_size=target_committee_size,
                shard_count=shard_count,
            )
        )
    )


def get_winning_root(
        *,
        state: 'BeaconState',
        shard: ShardNumber,
        attestations: Sequence[PendingAttestationRecord],
        genesis_epoch: EpochNumber,
        epoch_length: int,
        max_deposit_amount: Gwei,
        target_committee_size: int,
        shard_count: int) -> Tuple[Hash32, Gwei]:
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
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length,
            max_deposit_amount=max_deposit_amount,
            target_committee_size=target_committee_size,
            shard_count=shard_count,
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
