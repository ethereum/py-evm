from typing import (
    Tuple,
    Sequence,
)
from eth.beacon.typing import (
    Ether,
    Gwei,
    SlotNumber,
)
from eth.beacon.types.validator_records import ValidatorRecord
from eth.beacon.types.states import BeaconState
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.helpers import (
    get_effective_balance,
    get_active_validator_indices,
    get_attestation_participants,
    get_block_root,
    total_balance,
)
from eth.beacon.constants import TWO_POWER_64


def get_epoch_boundary_attesting_balances(
        state: BeaconState,
        config: BeaconConfig) -> Tuple[Gwei, Gwei]:
    """
    previous_epoch_boundary_attesting_balance:
        SELECT sum(v.balance)
        FROM Validator as v
        RIGHT JOIN Attestations as a
        ON v.index = a.participant
        WHERE
            a.slot between `now` and `2 epoch ago` AND
            a.justified_slot = previous_justified_slot AND
            a.epoch_boundary_root = `2 epoch ago`
        GROUP BY v.index

    current_epoch_boundary_attesting_balance:
        SELECT sum(v.balance)
        FROM Validator as v
        RIGHT JOIN Attestations as a
        ON v.index = a.participant
        WHERE
            a.slot between `now` and `1 epoch ago` AND
            a.justified_slot = justified_slot AND
            a.epoch_boundary_root = `1 epoch ago`
        GROUP BY v.index
    """

    EPOCH_LENGTH = config.EPOCH_LENGTH
    MAX_DEPOSIT = config.MAX_DEPOSIT
    LATEST_BLOCK_ROOTS_LENGTH = config.LATEST_BLOCK_ROOTS_LENGTH

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
        state,
        state.slot - 2 * EPOCH_LENGTH,
        LATEST_BLOCK_ROOTS_LENGTH)
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
    previous_epoch_boundary_attesting_balance = Gwei(sum(
        get_effective_balance(state, index, MAX_DEPOSIT)
        for index in previous_epoch_boundary_attester_indices
    ))

    current_epoch_boundary_root = get_block_root(
        state,
        state.slot - EPOCH_LENGTH,
        LATEST_BLOCK_ROOTS_LENGTH)

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

    current_epoch_boundary_attesting_balance = Gwei(sum(
        get_effective_balance(state, index, MAX_DEPOSIT)
        for index in current_epoch_boundary_attester_indices
    ))
    return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance


def get_total_balance(
        validator_registry: Sequence[ValidatorRecord],
        validator_balances: Sequence[Gwei],
        max_deposit: Ether) -> Gwei:

    active_validator_indices = get_active_validator_indices(validator_registry)

    return total_balance(active_validator_indices, validator_balances, max_deposit)


def check_finalization(previous_justified_slot: SlotNumber,
                       slot: SlotNumber,
                       justification_bitfield: int,
                       epoch_length: int)-> bool:

    # Suppose B1, B2, B3, B4 are consecutive blocks and
    # we are now processing the end of the cycle containing B4.

    # If B4 and is justified using source B3, then B3 is finalized.
    should_finalize_B3 = (
        previous_justified_slot == slot - 2 * epoch_length and
        justification_bitfield % 4 == 3
    )
    if should_finalize_B3:
        return True

    # If B4 is justified using source B2, and B3 has been justified,
    # then B2 is finalized.
    should_finalize_B2 = (
        previous_justified_slot == slot - 3 * epoch_length and
        justification_bitfield % 8 == 7
    )
    if should_finalize_B2:
        return True
    # If B3 is justified using source B1, and B1 has been justified,
    # then B1 is finalized.
    should_finalize_B1 = (
        previous_justified_slot == slot - 4 * epoch_length and
        justification_bitfield % 16 in (15, 14)
    )
    if should_finalize_B1:
        return True
    return False


def process_justification(state: BeaconState, config: BeaconConfig) -> BeaconState:
    EPOCH_LENGTH = config.EPOCH_LENGTH

    total_balance = get_total_balance(
        state.validator_registry,
        state.validator_balances,
        config.MAX_DEPOSIT,
    )
    (
        previous_epoch_boundary_attesting_balance,
        current_epoch_boundary_attesting_balance
    ) = get_epoch_boundary_attesting_balances(state, config)

    previous_justified_slot = state.justified_slot
    justified_slot = state.justified_slot
    justification_bitfield = int.from_bytes(state.justification_bitfield, 'big')
    finalized_slot = state.finalized_slot

    # Add two bits at the right of justification_bitfield. Cap it at 64 bits.
    justification_bitfield = (justification_bitfield * 2) % TWO_POWER_64

    if 3 * previous_epoch_boundary_attesting_balance >= 2 * total_balance:
        justification_bitfield |= 2
        justified_slot = state.slot - 2 * EPOCH_LENGTH
    if 3 * current_epoch_boundary_attesting_balance >= 2 * total_balance:
        justification_bitfield |= 1
        justified_slot = state.slot - 1 * EPOCH_LENGTH

    should_finalize = check_finalization(
        previous_justified_slot,
        state.slot,
        justification_bitfield,
        EPOCH_LENGTH,
    )
    if should_finalize:
        finalized_slot = previous_justified_slot

    return state.copy(
        previous_justified_slot=previous_justified_slot,
        justified_slot=justified_slot,
        justification_bitfield=justification_bitfield.to_bytes(8, 'big'),
        finalized_slot=finalized_slot,
    )
