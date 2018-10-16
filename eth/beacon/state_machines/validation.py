from typing import (
    Iterable,
    Sequence,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    ValidationError,
)

from eth.exceptions import (
    BlockNotFound,
)
from eth.utils import bls
from eth.utils.bitfield import (
    get_bitfield_length,
    has_voted,
)

from eth.beacon.aggregation import (
    create_signing_message,
)
from eth.beacon.helpers import (
    get_attestation_indices,
    get_block_committees_info,
    get_signed_parent_hashes,
)

from eth.beacon.db.chain import BaseBeaconChainDB  # noqa: F401

from eth.beacon.types.active_states import ActiveState  # noqa: F401
from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401
from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth.beacon.types.crystallized_states import CrystallizedState  # noqa: F401


#
# Parent block proposer validation
#
def validate_parent_block_proposer(crystallized_state: 'CrystallizedState',
                                   block: 'BaseBeaconBlock',
                                   parent_block: 'BaseBeaconBlock',
                                   cycle_length: int) -> None:
    if block.slot_number == 0:
        return

    block_committees_info = get_block_committees_info(
        parent_block,
        crystallized_state,
        cycle_length,
    )

    try:
        attestation = block.attestations[0]
    except IndexError:
        raise ValidationError(
            "block.attestations should not be an empty list"
        )

    is_proposer_attestation = (
        attestation.shard_id == block_committees_info.proposer_shard_id and
        attestation.slot == parent_block.slot_number and
        has_voted(
            attestation.attester_bitfield,
            block_committees_info.proposer_index_in_committee
        )
    )
    if not is_proposer_attestation:
        raise ValidationError(
            "Proposer of parent block should be one of the attesters in block.attestions[0]:\n"
            "\tExpected: proposer index in committee: %d, shard_id: %d, slot: %d\n"
            "\tFound: shard_id: %d, slot: %d, voted: %s" % (
                block_committees_info.proposer_index_in_committee,
                block_committees_info.proposer_shard_id,
                parent_block.slot_number,
                attestation.shard_id,
                attestation.slot,
                has_voted(
                    attestation.attester_bitfield,
                    block_committees_info.proposer_index_in_committee,
                ),
            )
        )


#
# Attestation validation
#
def validate_attestation(
        block: BaseBeaconBlock,
        parent_block: BaseBeaconBlock,
        crystallized_state: CrystallizedState,
        recent_block_hashes: Iterable[Hash32],
        attestation: 'AttestationRecord',
        chaindb: BaseBeaconChainDB,
        cycle_length: int,
        is_validating_signatures: bool=True) -> None:
    """
    Validate the given ``attestation``.

    Raise ``ValidationError`` if it's invalid.
    """
    validate_slot(
        parent_block,
        attestation,
        cycle_length,
    )

    validate_justified(
        crystallized_state,
        attestation,
        chaindb,
    )

    attestation_indices = get_attestation_indices(
        crystallized_state,
        attestation,
        cycle_length,
    )

    validate_bitfield(attestation, attestation_indices)

    # TODO: implement versioning
    validate_version(crystallized_state, attestation)

    if is_validating_signatures:
        parent_hashes = get_signed_parent_hashes(
            recent_block_hashes,
            block,
            attestation,
            cycle_length,
        )
        validate_aggregate_sig(
            crystallized_state,
            attestation,
            attestation_indices,
            parent_hashes,
        )


def validate_slot(parent_block: 'BaseBeaconBlock',
                  attestation: 'AttestationRecord',
                  cycle_length: int) -> None:
    """
    Validate ``slot`` field.

    Raise ``ValidationError`` if it's invalid.
    """
    if attestation.slot > parent_block.slot_number:
        raise ValidationError(
            "Attestation slot number too high:\n"
            "\tFound: %s Needed less than or equal to %s" %
            (attestation.slot, parent_block.slot_number)
        )
    if attestation.slot < max(parent_block.slot_number - cycle_length + 1, 0):
        raise ValidationError(
            "Attestation slot number too low:\n"
            "\tFound: %s, Needed greater than or equalt to: %s" %
            (
                attestation.slot,
                max(parent_block.slot_number - cycle_length + 1, 0)
            )
        )


def validate_justified(crystallized_state: 'CrystallizedState',
                       attestation: 'AttestationRecord',
                       chaindb: 'BaseBeaconChainDB') -> None:
    """
    Validate ``justified_slot`` and ``justified_block_hash`` fields.

    Raise ``ValidationError`` if it's invalid.
    """
    if attestation.justified_slot > crystallized_state.last_justified_slot:
        raise ValidationError(
            "attestation.justified_slot %s should be equal to or earlier than"
            " crystallized_state.last_justified_slot %s" % (
                attestation.justified_slot,
                crystallized_state.last_justified_slot,
            )
        )
    try:
        justified_block = chaindb.get_block_by_hash(attestation.justified_block_hash)
    except BlockNotFound:
        raise ValidationError(
            "justified_block_hash %s is not in the canonical chain" %
            attestation.justified_block_hash
        )
    if justified_block.slot_number != attestation.justified_slot:
        raise ValidationError(
            "justified_slot %s doesn't match justified_block_hash" % attestation.justified_slot
        )


def validate_bitfield(attestation: 'AttestationRecord',
                      attestation_indices: Sequence[int]) -> None:
    """
    Validate ``attester_bitfield`` field.

    Raise ``ValidationError`` if it's invalid.
    """
    if len(attestation.attester_bitfield) != get_bitfield_length(len(attestation_indices)):
        raise ValidationError(
            "Attestation has incorrect bitfield length. Found: %s, Expected: %s" %
            (len(attestation.attester_bitfield), get_bitfield_length(len(attestation_indices)))
        )

    # check if end bits are zero
    last_bit = len(attestation_indices)
    if last_bit % 8 != 0:
        for i in range(8 - last_bit % 8):
            if has_voted(attestation.attester_bitfield, last_bit + i):
                raise ValidationError("Attestation has non-zero trailing bits")


def validate_version(crystallized_state: 'CrystallizedState',
                     attestation: 'AttestationRecord') -> None:
    # TODO: it's a stub
    pass


def validate_aggregate_sig(crystallized_state: 'CrystallizedState',
                           attestation: 'AttestationRecord',
                           attestation_indices: Iterable[int],
                           parent_hashes: Iterable[Hash32]) -> None:
    """
    Validate ``aggregate_sig`` field.

    Raise ``ValidationError`` if it's invalid.
    """
    pub_keys = [
        crystallized_state.validators[validator_index].pubkey
        for committee_index, validator_index in enumerate(attestation_indices)
        if has_voted(attestation.attester_bitfield, committee_index)
    ]

    message = create_signing_message(
        attestation.slot,
        parent_hashes,
        attestation.shard_id,
        attestation.shard_block_hash,
        attestation.justified_slot,
    )
    if not bls.verify(message, bls.aggregate_pubs(pub_keys), attestation.aggregate_sig):
        raise ValidationError("Attestation aggregate signature fails")


#
# State roots validation
#
def validate_state_roots(crystallized_state_root: Hash32,
                         active_state_root: Hash32,
                         block: 'BaseBeaconBlock') -> None:
    """
    Validate block ``crystallized_state_root`` and ``active_state_root`` fields.

    Raise ``ValidationError`` if it's invalid.
    """
    if crystallized_state_root != block.crystallized_state_root:
        raise ValidationError(
            "Crystallized state root incorrect. Found: %s, Expected: %s" %
            (crystallized_state_root, block.crystallized_state_root)
        )
    if active_state_root != block.active_state_root:
        raise ValidationError(
            "Active state root incorrect. Found: %s, Expected: %s" %
            (active_state_root, block.active_state_root)
        )
