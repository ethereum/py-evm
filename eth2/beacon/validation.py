from eth_utils import (
    ValidationError,
)

from eth.validation import (
    validate_gte,
    validate_lte,
    validate_is_integer,
)

from eth2.beacon.typing import (
    SlotNumber,
)


def validate_slot(slot: int, title: str="Slot") -> None:
    validate_is_integer(slot, title)
    validate_gte(slot, 0, title)
    validate_lte(slot, 2**64 - 1, title)


def validate_slot_for_state_slot(
        state_slot: SlotNumber,
        slot: SlotNumber,
        epoch_length: int) -> None:
    state_epoch_slot = state_slot - (state_slot % epoch_length)

    if state_epoch_slot > slot + epoch_length:
        raise ValidationError(
            f"state_epoch_slot ({state_epoch_slot}) should be less than or equal to "
            f"slot ({slot}) + epoch_length ({epoch_length})"
        )

    if slot >= state_epoch_slot + epoch_length:
        raise ValidationError(
            f"slot ({slot}) should be less than "
            f"state_epoch_slot + epoch_length ({state_epoch_slot + epoch_length}), "
            f"where state_epoch_slot={state_epoch_slot}, epoch_length={epoch_length}"
        )


def validate_epoch_for_active_index_root(state_epoch: int,
                                         given_epoch: int,
                                         latest_index_roots_length: int) -> None:
    if state_epoch >= given_epoch + latest_index_roots_length:
        raise ValidationError(
            f"start_epoch ({state_epoch}) should be less than (given_epoch {given_epoch} + "
            f"LATEST_INDEX_ROOTS_LENGTH ({latest_index_roots_length}))"
        )

    if given_epoch > state_epoch:
        raise ValidationError(
            f"given_epoch ({given_epoch}) should be less than or equal to given_epoch {state_epoch}"
        )
