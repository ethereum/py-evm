from eth_utils import (
    ValidationError,
)

from eth2._utils.bitfield import (
    get_bitfield_length,
    has_voted,
)

from eth2.beacon.typing import (
    Epoch,
)


def validate_epoch_for_randao_mix(state_epoch: Epoch,
                                  given_epoch: Epoch,
                                  epochs_per_historical_vector: int) -> None:
    if state_epoch >= given_epoch + epochs_per_historical_vector:
        raise ValidationError(
            f"state_epoch ({state_epoch}) should be less than (given_epoch {given_epoch} + "
            f"EPOCHS_PER_HISTORICAL_VECTOR ({epochs_per_historical_vector}))"
        )

    if given_epoch > state_epoch:
        raise ValidationError(
            f"given_epoch ({given_epoch}) should be less than or equal to state_epoch {state_epoch}"
        )


def validate_epoch_for_active_index_root(state_epoch: Epoch,
                                         given_epoch: Epoch,
                                         activation_exit_delay: int,
                                         epochs_per_historical_vector: int) -> None:
    lower_bound = state_epoch - epochs_per_historical_vector + activation_exit_delay
    if given_epoch <= lower_bound:
        raise ValidationError(
            f"state_epoch ({state_epoch}) should be less than (given_epoch {given_epoch} + "
            f"EPOCHS_PER_HISTORICAL_VECTOR ({epochs_per_historical_vector}))"
        )

    upper_bound = state_epoch + activation_exit_delay
    if upper_bound < given_epoch:
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
