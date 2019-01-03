from typing import Tuple
from eth.beacon.typing import Gwei
from eth.beacon.types.states import BeaconState
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.helpers import (
    get_effective_balance,
    get_active_validator_indices,
    get_attestation_participants,
    get_block_root,
)


def epoch_boundary_attesting_balances(
        state: BeaconState,
        config: BeaconConfig) -> Tuple[Gwei, Gwei]:
    EPOCH_LENGTH = config.EPOCH_LENGTH
    MAX_DEPOSITS = config.MAX_DEPOSITS

    current_epoch_attestations = tuple(
        attestation
        for attestation in state.latest_attestations
        if state.slot - EPOCH_LENGTH <= attestation.data.slot < state.slot
    )
    previous_epoch_attestations = tuple(
        attestation
        for attestation in state.latest_attestations
        if state.slot - 2 * EPOCH_LENGTH <= attestation.data.slot < state.slot - EPOCH_LENGTH
    )

    previous_epoch_justified_attestations = tuple(
        attestation
        for attestation in current_epoch_attestations + previous_epoch_attestations
        if attestation.justified_slot == state.previous_justified_slot
    )

    previous_epoch_boundary_root = get_block_root(
        state.latest_block_roots,
        state.slot,
        state.slot - 2 * EPOCH_LENGTH)
    previous_epoch_boundary_attestations = tuple(
        attestation
        for attestation in previous_epoch_justified_attestations
        if attestation.epoch_boundary_root == previous_epoch_boundary_root
    )

    sets_of_previous_epoch_boundary_participants = tuple(
        frozenset(get_attestation_participants(
            state,
            attestation.data.slot,
            attestation.data.shard,
            attestation.participation_bitfield,
            EPOCH_LENGTH,
        ))
        for attestation in previous_epoch_boundary_attestations
    )
    previous_epoch_boundary_attester_indices = (
        tuple()
        if len(sets_of_previous_epoch_boundary_participants) == 0
        else frozenset.union(*sets_of_previous_epoch_boundary_participants)
    )
    previous_epoch_boundary_attesting_balance = sum(
        get_effective_balance(state, index, MAX_DEPOSITS)
        for index in previous_epoch_boundary_attester_indices
    )

    current_epoch_boundary_root = get_block_root(
        state.latest_block_roots,
        state.slot,
        state.slot - EPOCH_LENGTH)

    current_epoch_boundary_attestations = tuple(
        attestation
        for attestation in current_epoch_attestations
        if attestation.epoch_boundary_root == current_epoch_boundary_root and
        attestation.data.justified_slot == state.justified_slot
    )

    sets_of_current_epoch_boundary_participants = tuple(
        frozenset(get_attestation_participants(
            state,
            attestation.data.slot,
            attestation.data.shard,
            attestation.participation_bitfield,
            EPOCH_LENGTH,
        ))
        for attestation in current_epoch_boundary_attestations
    )

    current_epoch_boundary_attester_indices = (
        tuple()
        if len(sets_of_current_epoch_boundary_participants) == 0
        else frozenset.union(*sets_of_current_epoch_boundary_participants)
    )

    current_epoch_boundary_attesting_balance = sum(
        get_effective_balance(state, index, MAX_DEPOSITS)
        for index in current_epoch_boundary_attester_indices
    )
    return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance


def process_justification(state: BeaconState, config: BeaconConfig) -> BeaconState:
    EPOCH_LENGTH = config.EPOCH_LENGTH
    MAX_DEPOSITS = config.MAX_DEPOSITS

    active_validator_indices = get_active_validator_indices(state.validator_registry)

    total_balance = sum(
        get_effective_balance(
            state.validator_balances,
            index,
            MAX_DEPOSITS)
        for index in active_validator_indices
    )

    (
        previous_epoch_boundary_attesting_balance,
        current_epoch_boundary_attesting_balance
    ) = epoch_boundary_attesting_balances(state, config)

    previous_justified_slot = state.justified_slot
    justified_slot = state.justified_slot
    justification_bitfield = int.from_bytes(state.justification_bitfield, 'big')
    finalized_slot = state.finalized_slot

    justification_bitfield = (justification_bitfield * 2) % 2**64

    if 3 * previous_epoch_boundary_attesting_balance >= 2 * total_balance:
        justification_bitfield |= 2
        justified_slot = state.slot - 2 * EPOCH_LENGTH
    if 3 * current_epoch_boundary_attesting_balance >= 2 * total_balance:
        justification_bitfield |= 1
        justified_slot = state.slot - 1 * EPOCH_LENGTH
    if any([
        (
            previous_justified_slot == state.slot - 2 * EPOCH_LENGTH and
            justification_bitfield % 4 == 3
        ),
        (
            previous_justified_slot == state.slot - 3 * EPOCH_LENGTH and
            justification_bitfield % 8 == 7
        ),
        (
            previous_justified_slot == state.slot - 4 * EPOCH_LENGTH and
            justification_bitfield % 16 in (15, 14)
        ),
    ]):
        finalized_slot = previous_justified_slot

    return state.copy(
        previous_justified_slot=previous_justified_slot,
        justified_slot=justified_slot,
        justification_bitfield=justification_bitfield.to_bytes(8, 'big'),
        finalized_slot=finalized_slot,
    )
