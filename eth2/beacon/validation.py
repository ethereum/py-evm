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
            "state_epoch_slot ({}) should be less than or equal to slot + "
            "epoch_length ({})".format(
                state_epoch_slot,
                slot + epoch_length,
            )
        )
    if slot >= state_epoch_slot + epoch_length:
        raise ValidationError(
            "slot ({}) should be less than "
            "state_epoch_slot + epoch_length ({}), "
            "where state_epoch_slot={}, epoch_length={}".format(
                slot,
                state_epoch_slot + epoch_length,
                state_epoch_slot,
                epoch_length,
            )
        )
