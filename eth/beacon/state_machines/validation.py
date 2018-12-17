from typing import (
    Sequence,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    ValidationError,
)


from eth.beacon.helpers import (
    get_block_hash,
)
from eth.beacon.types.states import BeaconState  # noqa: F401


#
# Attestation validation
#
def validate_attestation(state: BeaconState,
                         attestation: 'AttestationRecord',
                         epoch_length: int,
                         min_attestation_inclusion_delay: int,
                         is_validating_signatures: bool=True) -> None:
    """
    Validate the given ``attestation``.
    Raise ``ValidationError`` if it's invalid.
    """

    validate_attestation_slot(
        attestation_data=attestation.data,
        current_slot=state.slot,
        epoch_length=epoch_length,
        min_attestation_inclusion_delay=min_attestation_inclusion_delay,
    )

    validate_attestation_justified_slot(
        attestation_data=attestation.data,
        current_slot=state.slot,
        previous_justified_slot=state.previous_justified_slot,
        justified_slot=state.justified_slot,
        epoch_length=epoch_length,
    )

    validate_attestation_justified_block_root(
        attestation_data=attestation.data,
        justified_block_root=get_block_hash(
            state.latest_block_hashes,
            current_slot=state.slot,
            slot=attestation.data.justified_slot,
        ),
    )

    validate_attestation_latest_crosslink_root(
        attestation,
        state.latest_crosslinks[attestation.data.shard].shard_block_root,
    )

    if is_validating_signatures:
        validate_attestation_aggregate_signature(
            state,
            attestation,
        )


def validate_attestation_slot(attestation_data: 'AttestationData',
                              current_slot: int,
                              epoch_length: int,
                              min_attestation_inclusion_delay: int) -> None:
    """
    Validate ``slot`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.slot + min_attestation_inclusion_delay > current_slot:
        raise ValidationError(
            "Attestation slot plus min inclusion delay is too high:\n"
            "\tFound: %s (%s + %s), Needed less than or equal to %s" %
            (
                attestation_data.slot + min_attestation_inclusion_delay,
                attestation_data.slot,
                min_attestation_inclusion_delay,
                current_slot,
            )
        )
    if attestation_data.slot + epoch_length < current_slot:
        raise ValidationError(
            "Attestation slot plus epoch length is too low:\n"
            "\tFound: %s (%s + %s), Needed greater than or equal to: %s" %
            (
                attestation_data.slot + epoch_length,
                attestation_data.slot,
                epoch_length,
                current_slot,
            )
        )


def validate_attestation_justified_slot(attestation_data: 'AttestationData',
                                        current_slot: int,
                                        previous_justified_slot: int,
                                        justified_slot: int,
                                        epoch_length: int) -> None:
    if attestation_data.slot >= current_slot - (current_slot % epoch_length):
        if attestation_data.justified_slot != justified_slot:
            raise ValidationError(
                "Attestation slot is after recent epoch transition but "
                "is not targeting the justified slot:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_slot, justified_slot)
            )
    else:
        if attestation_data.justified_slot != previous_justified_slot:
            raise ValidationError(
                "Attestation slot is before recent epoch transition but "
                "is not targeting the previous justified slot:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_slot, previous_justified_slot)
            )


def validate_attestation_justified_block_root(attestation_data: 'AttestationData',
                                              justified_block_root: Hash32) -> None:
    if attestation_data.justified_block_hash != justified_block_root:
        raise ValidationError(
            "Attestation justified block root is not equal to the block root at the "
            "justified slot:\n"
            "\tFound: %s, Expected %s at slot %s" %
            (
                attestation_data.justified_block_hash,
                justified_block_root,
                attestation_data.justified_slot,
            )
        )


def validate_attestation_latest_crosslink_root(attestation_data: 'AttestationData',
                                               latest_crosslink_shard_block_root: Hash32) -> None:
    pass


def validate_attestation_aggregate_signature(state: BeaconState,
                                             attestation: 'AttestationRecord') -> None:
    pass
