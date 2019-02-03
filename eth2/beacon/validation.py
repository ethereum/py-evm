from eth_utils import (
    ValidationError,
)

from eth.validation import (
    validate_gte,
    validate_lte,
    validate_is_integer,
)

from eth2.beacon.typing import (
    EpochNumber,
    SlotNumber,
)


def validate_slot(slot: int, title: str="Slot") -> None:
    validate_is_integer(slot, title)
    validate_gte(slot, 0, title)
    validate_lte(slot, 2**64 - 1, title)


def validate_epoch_for_current_epoch(
        current_epoch: EpochNumber,
        epoch: EpochNumber,
        genesis_epoch: EpochNumber,
        epoch_length: int) -> None:
    previous_epoch = current_epoch - 1 if current_epoch > genesis_epoch else current_epoch
    next_epoch = current_epoch + 1

    if epoch < previous_epoch:
        raise ValidationError(
            f"previous_epoch ({previous_epoch}) should be less than or equal to epoch ({epoch})"
        )

    if epoch >= next_epoch:
        raise ValidationError(
            f"epoch ({epoch}) should be less than next_epoch ({next_epoch})"
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
