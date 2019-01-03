from eth_typing import (
    Hash32
)
from eth_utils import (
    ValidationError,
)
import rlp

from eth.constants import (
    ZERO_HASH32,
)

from eth._utils import bls as bls
from eth.beacon._utils.hash import (
    hash_eth2,
)

from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.helpers import (
    get_attestation_participants,
    get_beacon_proposer_index,
    get_block_root,
    get_domain,
)
from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth.beacon.types.states import BeaconState  # noqa: F401
from eth.beacon.types.attestations import Attestation  # noqa: F401
from eth.beacon.types.attestation_data import AttestationData  # noqa: F401
from eth.beacon.types.proposal_signed_data import ProposalSignedData
from eth.beacon.typing import (
    ShardNumber,
)


#
# Proposer signature validation
#
def validate_serenity_proposer_signature(state: BeaconState,
                                         block: BaseBeaconBlock,
                                         beacon_chain_shard_number: ShardNumber,
                                         epoch_length: int) -> None:
    block_without_signature_root = block.block_without_signature_root

    # TODO: Replace this root with tree hash root
    proposal_root = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        block_without_signature_root,
    ).root

    # Get the public key of proposer
    beacon_proposer_index = get_beacon_proposer_index(state, state.slot, epoch_length)
    proposer_pubkey = state.validator_registry[beacon_proposer_index].pubkey

    is_valid_signature = bls.verify(
        pubkey=proposer_pubkey,
        message=proposal_root,
        signature=block.signature,
        domain=get_domain(state.fork_data, state.slot, SignatureDomain.DOMAIN_PROPOSAL),
    )

    if not is_valid_signature:
        raise ValidationError("Invalid Proposer Signature on block")


#
# Attestation validation
#
def validate_serenity_attestation(state: BeaconState,
                                  attestation: Attestation,
                                  epoch_length: int,
                                  min_attestation_inclusion_delay: int,
                                  latest_block_roots_length: int) -> None:
    """
    Validate the given ``attestation``.
    Raise ``ValidationError`` if it's invalid.
    """

    validate_serenity_attestation_slot(
        attestation.data,
        state.slot,
        epoch_length,
        min_attestation_inclusion_delay,
    )

    validate_serenity_attestation_justified_slot(
        attestation.data,
        state.slot,
        state.previous_justified_slot,
        state.justified_slot,
        epoch_length,
    )

    validate_serenity_attestation_justified_block_root(
        attestation.data,
        justified_block_root=get_block_root(
            state=state,
            slot=attestation.data.justified_slot,
            latest_block_roots_length=latest_block_roots_length,
        ),
    )

    validate_serenity_attestation_latest_crosslink_root(
        attestation.data,
        latest_crosslink_root=state.latest_crosslinks[attestation.data.shard].shard_block_root,
    )

    validate_serenity_attestation_shard_block_root(attestation.data)

    validate_serenity_attestation_aggregate_signature(
        state,
        attestation,
        epoch_length,
    )


def validate_serenity_attestation_slot(attestation_data: AttestationData,
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


def validate_serenity_attestation_justified_slot(attestation_data: AttestationData,
                                                 current_slot: int,
                                                 previous_justified_slot: int,
                                                 justified_slot: int,
                                                 epoch_length: int) -> None:
    """
    Validate ``justified_slot`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.slot >= current_slot - (current_slot % epoch_length):
        if attestation_data.justified_slot != justified_slot:
            raise ValidationError(
                "Attestation ``slot`` is after recent epoch transition but attestation"
                "``justified_slot`` is not targeting the ``justified_slot``:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_slot, justified_slot)
            )
    else:
        if attestation_data.justified_slot != previous_justified_slot:
            raise ValidationError(
                "Attestation ``slot`` is before recent epoch transition but attestation"
                "``justified_slot`` is not targeting the ``previous_justified_slot:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_slot, previous_justified_slot)
            )


def validate_serenity_attestation_justified_block_root(attestation_data: AttestationData,
                                                       justified_block_root: Hash32) -> None:
    """
    Validate ``justified_block_root`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.justified_block_root != justified_block_root:
        raise ValidationError(
            "Attestation ``justified_block_root`` is not equal to the "
            "``justified_block_root`` at the ``justified_slot``:\n"
            "\tFound: %s, Expected %s at slot %s" %
            (
                attestation_data.justified_block_root,
                justified_block_root,
                attestation_data.justified_slot,
            )
        )


def validate_serenity_attestation_latest_crosslink_root(attestation_data: AttestationData,
                                                        latest_crosslink_root: Hash32) -> None:
    """
    Validate that either the attestation ``latest_crosslink_root`` or ``shard_block_root``
    field of ``attestation_data`` is the provided ``latest_crosslink_root``.
    Raise ``ValidationError`` if it's invalid.
    """
    acceptable_shard_block_roots = {
        attestation_data.latest_crosslink_root,
        attestation_data.shard_block_root,
    }
    if latest_crosslink_root not in acceptable_shard_block_roots:
        raise ValidationError(
            "Neither the attestation ``latest_crosslink_root`` nor the attestation "
            "``shard_block_root`` are equal to the ``latest_crosslink_root``.\n"
            "\tFound: %s and %s, Expected %s" %
            (
                attestation_data.latest_crosslink_root,
                attestation_data.shard_block_root,
                latest_crosslink_root,
            )
        )


def validate_serenity_attestation_shard_block_root(attestation_data: AttestationData) -> None:
    """
    Validate ``shard_block_root`` field of `attestation_data`.
    Raise ``ValidationError`` if it's invalid.

    Note: This is the Phase 0 version of ``shard_block_root`` validation.
    This is a built-in stub and will be changed in phase 1.
    """
    if attestation_data.shard_block_root != ZERO_HASH32:
        raise ValidationError(
            "Attestation ``shard_block_root`` is not ZERO_HASH32.\n"
            "\tFound: %s, Expected %s" %
            (
                attestation_data.shard_block_root,
                ZERO_HASH32,
            )
        )


def validate_serenity_attestation_aggregate_signature(state: BeaconState,
                                                      attestation: Attestation,
                                                      epoch_length: int) -> None:
    """
    Validate ``aggregate_signature`` field of ``attestation``.
    Raise ``ValidationError`` if it's invalid.

    Note: This is the phase 0 version of `aggregate_signature`` validation.
    All proof of custody bits are assumed to be 0 within the signed data.
    This will change to reflect real proof of custody bits in the Phase 1.
    """
    participant_indices = get_attestation_participants(
        state=state,
        slot=attestation.data.slot,
        shard=attestation.data.shard,
        participation_bitfield=attestation.participation_bitfield,
        epoch_length=epoch_length,
    )

    pubkeys = tuple(
        state.validator_registry[validator_index].pubkey
        for validator_index in participant_indices
    )
    group_public_key = bls.aggregate_pubkeys(pubkeys)

    # TODO: change to tree hashing when we have SSZ
    # TODO: Replace with AttestationAndCustodyBit data structure
    message = hash_eth2(
        rlp.encode(attestation.data) +
        (0).to_bytes(1, "big")
    )

    is_valid_signature = bls.verify(
        message=message,
        pubkey=group_public_key,
        signature=attestation.aggregate_signature,
        domain=get_domain(
            fork_data=state.fork_data,
            slot=attestation.data.slot,
            domain_type=SignatureDomain.DOMAIN_ATTESTATION,
        ),

    )
    if not is_valid_signature:
        raise ValidationError(
            "Attestation ``aggregate_signature`` is invalid."
        )
