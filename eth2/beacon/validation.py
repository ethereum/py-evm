from eth_utils import (
    ValidationError,
)

from eth.validation import (
    validate_gte,
    validate_lte,
    validate_is_integer,
)

from eth2._utils.bitfield import (
    get_bitfield_length,
    has_voted,
)

from eth2.beacon.typing import (
    EpochNumber,
)


def validate_slot(slot: int, title: str="Slot") -> None:
    validate_is_integer(slot, title)
    validate_gte(slot, 0, title)
    validate_lte(slot, 2**64 - 1, title)


def validate_epoch_for_current_epoch(
        current_epoch: EpochNumber,
        given_epoch: EpochNumber,
        genesis_epoch: EpochNumber) -> None:
    previous_epoch = current_epoch - 1 if current_epoch > genesis_epoch else current_epoch
    next_epoch = current_epoch + 1

    if given_epoch < previous_epoch:
        raise ValidationError(
            f"previous_epoch ({previous_epoch}) should be less than "
            f"or equal to given_epoch ({given_epoch})"
        )

    if given_epoch > next_epoch:
        raise ValidationError(
            f"given_epoch ({given_epoch}) should be less than next_epoch ({next_epoch})"
        )


def validate_epoch_for_active_randao_mix(state_epoch: EpochNumber,
                                         given_epoch: EpochNumber,
                                         latest_randao_mixes_length: int) -> None:
    if state_epoch >= given_epoch + latest_randao_mixes_length:
        raise ValidationError(
            f"state_epoch ({state_epoch}) should be less than (given_epoch {given_epoch} + "
            f"LATEST_RANDAO_MIXED_LENGTH ({latest_randao_mixes_length}))"
        )

    if given_epoch > state_epoch:
        raise ValidationError(
            f"given_epoch ({given_epoch}) should be less than or equal to state_epoch {state_epoch}"
        )


def validate_epoch_for_active_index_root(state_epoch: EpochNumber,
                                         given_epoch: EpochNumber,
                                         entry_exit_delay: int,
                                         latest_index_roots_length: int) -> None:
    if state_epoch >= given_epoch + latest_index_roots_length - entry_exit_delay:
        raise ValidationError(
            f"state_epoch ({state_epoch}) should be less than (given_epoch {given_epoch} + "
            f"LATEST_INDEX_ROOTS_LENGTH ({latest_index_roots_length}))"
        )

    if given_epoch > state_epoch + entry_exit_delay:
        raise ValidationError(
            f"given_epoch ({given_epoch}) should be less than or equal to state_epoch {state_epoch}"
        )


def validate_bitfield(bitfield: bytes, committee_size: int) -> None:
    """
    Verify ``bitfield`` against the ``committee_size``.
    """
    if len(bitfield) != get_bitfield_length(committee_size):
        raise ValidationError(
            f"len(bitfield) ({len(bitfield)}) != "
            f"get_bitfield_length(committee_size) ({get_bitfield_length(committee_size)}), "
            f"where committee_size={committee_size}"
        )

    for i in range(committee_size, len(bitfield) * 8):
        if has_voted(bitfield, i):
            raise ValidationError(f"bit ({i}) should be zero")
