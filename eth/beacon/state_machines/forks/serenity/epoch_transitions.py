from eth.beacon.types.states import BeaconState
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.helpers import (
    get_effective_balance,
    get_active_validator_indices,
    get_attestation_participants,
    get_block_root,
)


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
    current_epoch_attestations = [
        attestation
        for attestation in state.latest_attestations
        if state.slot - EPOCH_LENGTH <= attestation.data.slot < state.slot
    ]
    previous_epoch_attestations = [
        attestation
        for attestation in state.latest_attestations
        if state.slot - 2 * EPOCH_LENGTH <= attestation.data.slot < state.slot - EPOCH_LENGTH
    ]

    previous_epoch_justified_attestations = [
        attestation
        for attestation in current_epoch_attestations + previous_epoch_attestations
        if attestation.justified_slot == state.previous_justified_slot
    ]
    previous_epoch_boundary_attestations = [
        attestation
        for attestation in previous_epoch_justified_attestations
        if attestation.epoch_boundary_root == get_block_root(
            config.LATEST_BLOCK_ROOTS_LENGTH,
            state.slot,
            state.slot - 2 * EPOCH_LENGTH)
    ]
    previous_epoch_boundary_attester_indices = frozenset.union(*[
        get_attestation_participants(
            state,
            attestation.data.slot,
            attestation.data.shard,
            attestation.participation_bitfield,
            EPOCH_LENGTH,
        )
        for attestation in previous_epoch_boundary_attestations
    ])
    previous_epoch_boundary_attesting_balance = sum(
        get_effective_balance(state, index, MAX_DEPOSITS)
        for index in previous_epoch_boundary_attester_indices
    )

    current_epoch_boundary_attestations = [
        attestation
        for attestation in current_epoch_attestations
        if attestation.epoch_boundary_root == get_block_root(
            config.LATEST_BLOCK_ROOTS_LENGTH,
            state.slot,
            state.slot - EPOCH_LENGTH) and
        attestation.data.justified_slot == state.justified_slot
    ]

    current_epoch_boundary_attester_indices = frozenset.union(*[
        get_attestation_participants(
            state,
            attestation.data.slot,
            attestation.data.shard,
            attestation.participation_bitfield,
            EPOCH_LENGTH,
        )
        for attestation in current_epoch_boundary_attestations
    ])

    current_epoch_boundary_attesting_balance = sum(
        get_effective_balance(state, index, MAX_DEPOSITS)
        for index in current_epoch_boundary_attester_indices
    )

    state.previous_justified_slot = state.justified_slot
    state.justification_bitfield = (state.justification_bitfield * 2) % 2**64

    if 3 * previous_epoch_boundary_attesting_balance >= 2 * total_balance:
        state.justification_bitfield |= 2
        state.justified_slot = state.slot - 2 * EPOCH_LENGTH
    if 3 * current_epoch_boundary_attesting_balance >= 2 * total_balance:
        state.justification_bitfield |= 1
        state.justified_slot = state.slot - 1 * EPOCH_LENGTH
    if any(
        state.previous_justified_slot == state.slot - 2 *
        EPOCH_LENGTH and state.justification_bitfield % 4 == 3,
        state.previous_justified_slot == state.slot - 3 *
        EPOCH_LENGTH and state.justification_bitfield % 8 == 7,
        state.previous_justified_slot == state.slot - 4 *
        EPOCH_LENGTH and state.justification_bitfield % 16 in (15, 14),
    ):
        state.finalized_slot = state.previous_justified_slot

    return state
