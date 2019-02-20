import functools
from typing import (
    Iterable,
    Sequence,
    TYPE_CHECKING,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils import (
    bls,
    bitfield,
)

from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_crosslink_committee_for_attestation,
    get_members_from_bitfield,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.helpers import (
    get_epoch_start_slot,
    get_block_root,
    get_domain,
    slot_to_epoch,
)
from eth2.beacon.types.attestations import Attestation  # noqa: F401
from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
from eth2.beacon.types.attestation_data_and_custody_bits import AttestationDataAndCustodyBit
from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth2.beacon.types.forks import Fork  # noqa: F401
from eth2.beacon.types.proposal_signed_data import ProposalSignedData
from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState  # noqa: F401
from eth2.beacon.typing import (
    Bitfield,
    BLSPubkey,
    BLSSignature,
    EpochNumber,
    ShardNumber,
    SlotNumber,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
)

if TYPE_CHECKING:
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


#
# Slot validatation
#
def validate_block_slot(state: BeaconState,
                        block: BaseBeaconBlock) -> None:
    if block.slot != state.slot:
        raise ValidationError(
            f"block.slot ({block.slot}) is not equal to state.slot ({state.slot})"
        )


#
# Proposer signature validation
#
def validate_proposer_signature(state: BeaconState,
                                block: BaseBeaconBlock,
                                beacon_chain_shard_number: ShardNumber,
                                committee_config: CommitteeConfig) -> None:
    block_without_signature_root = block.block_without_signature_root

    # TODO: Replace this root with tree hash root
    proposal_root = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        block_without_signature_root,
    ).root

    # Get the public key of proposer
    beacon_proposer_index = get_beacon_proposer_index(
        state,
        state.slot,
        committee_config,
    )
    proposer_pubkey = state.validator_registry[beacon_proposer_index].pubkey
    domain = get_domain(
        state.fork,
        state.current_epoch(committee_config.EPOCH_LENGTH),
        SignatureDomain.DOMAIN_PROPOSAL
    )

    is_valid_signature = bls.verify(
        pubkey=proposer_pubkey,
        message=proposal_root,
        signature=block.signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            f"Invalid Proposer Signature on block, beacon_proposer_index={beacon_proposer_index}, "
            f"pubkey={proposer_pubkey}, message={proposal_root},"
            f"block.signature={block.signature}, domain={domain}"
        )


#
# Proposer slashing validation
#
def validate_proposer_slashing(state: BeaconState,
                               proposer_slashing: ProposerSlashing,
                               epoch_length: int) -> None:
    """
    Validate the given ``proposer_slashing``.
    Raise ``ValidationError`` if it's invalid.
    """
    proposer = state.validator_registry[proposer_slashing.proposer_index]

    validate_proposer_slashing_slot(proposer_slashing)

    validate_proposer_slashing_shard(proposer_slashing)

    validate_proposer_slashing_block_root(proposer_slashing)

    validate_proposer_slashing_slashed_epoch(
        proposer.slashed_epoch,
        state.current_epoch(epoch_length),
    )

    validate_proposal_signature(
        proposal_signed_data=proposer_slashing.proposal_data_1,
        proposal_signature=proposer_slashing.proposal_signature_1,
        pubkey=proposer.pubkey,
        fork=state.fork,
        epoch_length=epoch_length,
    )

    validate_proposal_signature(
        proposal_signed_data=proposer_slashing.proposal_data_2,
        proposal_signature=proposer_slashing.proposal_signature_2,
        pubkey=proposer.pubkey,
        fork=state.fork,
        epoch_length=epoch_length,
    )


def validate_proposer_slashing_slot(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_data_1.slot != proposer_slashing.proposal_data_2.slot:
        raise ValidationError(
            f"proposer_slashing.proposal_data_1.slot ({proposer_slashing.proposal_data_1.slot}) !="
            f" proposer_slashing.proposal_data_2.slot ({proposer_slashing.proposal_data_2.slot})"
        )


def validate_proposer_slashing_shard(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_data_1.shard != proposer_slashing.proposal_data_2.shard:
        raise ValidationError(
            f"proposer_slashing.proposal_data_1.shard ({proposer_slashing.proposal_data_1.shard}) "
            f"!= proposer_slashing.proposal_data_2.shard"
            f" ({proposer_slashing.proposal_data_2.shard})"
        )


def validate_proposer_slashing_block_root(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_data_1.block_root == proposer_slashing.proposal_data_2.block_root:
        raise ValidationError(
            "proposer_slashing.proposal_data_1.block_root "
            f"({proposer_slashing.proposal_data_1.block_root}) "
            "should not be equal to proposer_slashing.proposal_data_2.block_root "
            f"({proposer_slashing.proposal_data_2.block_root})"
        )


def validate_proposer_slashing_slashed_epoch(proposer_slashed_epoch: EpochNumber,
                                             state_current_epoch: EpochNumber) -> None:
    if proposer_slashed_epoch <= state_current_epoch:
        raise ValidationError(
            f"proposer.slashed_epoch ({proposer_slashed_epoch}) "
            f"should be greater than current epoch ({state_current_epoch})"
        )


def validate_proposal_signature(proposal_signed_data: ProposalSignedData,
                                proposal_signature: BLSSignature,
                                pubkey: BLSPubkey,
                                fork: Fork,
                                epoch_length: int) -> None:
    proposal_signature_is_valid = bls.verify(
        pubkey=pubkey,
        message=proposal_signed_data.root,  # TODO: use hash_tree_root
        signature=proposal_signature,
        domain=get_domain(
            fork,
            slot_to_epoch(proposal_signed_data.slot, epoch_length),
            SignatureDomain.DOMAIN_PROPOSAL,
        )
    )
    if not proposal_signature_is_valid:
        raise ValidationError(
            "Proposal signature is invalid: "
            f"proposer pubkey: {pubkey}, message: {proposal_signed_data.root}, "
            f"signature: {proposal_signature}"
        )


#
# Attestation validation
#
def validate_attestation(state: BeaconState,
                         attestation: Attestation,
                         min_attestation_inclusion_delay: int,
                         latest_block_roots_length: int,
                         committee_config: CommitteeConfig) -> None:
    """
    Validate the given ``attestation``.
    Raise ``ValidationError`` if it's invalid.
    """
    epoch_length = committee_config.EPOCH_LENGTH

    validate_attestation_slot(
        attestation.data,
        state.slot,
        epoch_length,
        min_attestation_inclusion_delay,
    )

    validate_attestation_justified_epoch(
        attestation.data,
        state.current_epoch(epoch_length),
        state.previous_justified_epoch,
        state.justified_epoch,
        epoch_length,
    )

    validate_attestation_justified_block_root(
        attestation.data,
        justified_block_root=get_block_root(
            state=state,
            slot=get_epoch_start_slot(
                attestation.data.justified_epoch,
                epoch_length,
            ),
            latest_block_roots_length=latest_block_roots_length,
        ),
    )

    validate_attestation_latest_crosslink_root(
        attestation.data,
        latest_crosslink_root=state.latest_crosslinks[attestation.data.shard].shard_block_root,
    )

    validate_attestation_shard_block_root(attestation.data)

    validate_attestation_aggregate_signature(
        state,
        attestation,
        committee_config,
    )


def validate_attestation_slot(attestation_data: AttestationData,
                              current_slot: SlotNumber,
                              epoch_length: int,
                              min_attestation_inclusion_delay: int) -> None:
    """
    Validate ``slot`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.slot > current_slot - min_attestation_inclusion_delay:
        raise ValidationError(
            "Attestation slot is greater than the ``current_slot`` less the "
            "``min_attestation_inclusion_delay``:\n"
            "\tFound: %s, Needed less than or equal to %s (%s - %s)" %
            (
                attestation_data.slot,
                current_slot - min_attestation_inclusion_delay,
                current_slot,
                min_attestation_inclusion_delay,
            )
        )
    if current_slot - min_attestation_inclusion_delay >= attestation_data.slot + epoch_length:
        raise ValidationError(
            "Attestation slot plus epoch length is too low; "
            "must equal or exceed the ``current_slot`` less the "
            "``min_attestation_inclusion_delay``:\n"
            "\tFound: %s (%s + %s), Needed greater than or equal to: %s (%s - %s)" %
            (
                attestation_data.slot + epoch_length,
                attestation_data.slot,
                epoch_length,
                current_slot - min_attestation_inclusion_delay,
                current_slot,
                min_attestation_inclusion_delay,
            )
        )


def validate_attestation_justified_epoch(attestation_data: AttestationData,
                                         current_epoch: EpochNumber,
                                         previous_justified_epoch: EpochNumber,
                                         justified_epoch: EpochNumber,
                                         epoch_length: int) -> None:
    """
    Validate ``justified_epoch`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.slot >= get_epoch_start_slot(current_epoch, epoch_length):
        if attestation_data.justified_epoch != justified_epoch:
            raise ValidationError(
                "Attestation ``slot`` is after recent epoch transition but attestation"
                "``justified_epoch`` is not targeting the ``justified_epoch``:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_epoch, justified_epoch)
            )
    else:
        if attestation_data.justified_epoch != previous_justified_epoch:
            raise ValidationError(
                "Attestation ``slot`` is before recent epoch transition but attestation"
                "``justified_epoch`` is not targeting the ``previous_justified_epoch:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.justified_epoch, previous_justified_epoch)
            )


def validate_attestation_justified_block_root(attestation_data: AttestationData,
                                              justified_block_root: Hash32) -> None:
    """
    Validate ``justified_block_root`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.justified_block_root != justified_block_root:
        raise ValidationError(
            "Attestation ``justified_block_root`` is not equal to the "
            "``justified_block_root`` at the ``justified_epoch``:\n"
            "\tFound: %s, Expected %s at slot %s" %
            (
                attestation_data.justified_block_root,
                justified_block_root,
                attestation_data.justified_epoch,
            )
        )


def validate_attestation_latest_crosslink_root(attestation_data: AttestationData,
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


def validate_attestation_shard_block_root(attestation_data: AttestationData) -> None:
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


@to_tuple
def get_pubkey_for_indices(validators: Sequence['ValidatorRecord'],
                           indices: Sequence[ValidatorIndex]) -> Iterable[BLSPubkey]:
    for index in indices:
        yield validators[index].pubkey


@to_tuple
def generate_aggregate_pubkeys_from_indices(
        validators: Sequence['ValidatorRecord'],
        *indices: Sequence[Sequence['ValidatorIndex']]) -> Iterable[BLSPubkey]:
    get_pubkeys = functools.partial(get_pubkey_for_indices, validators)
    return map(
        bls.aggregate_pubkeys,
        map(get_pubkeys, indices),
    )


def _validate_custody_bitfield(custody_bitfield: Bitfield) -> None:
    # NOTE: to be removed in phase 1.
    empty_custody_bitfield = b'\x00' * len(custody_bitfield)
    if custody_bitfield != empty_custody_bitfield:
        raise ValidationError(
            "Attestation custody bitfield is not empty.\n"
            f"\tFound: {custody_bitfield}, Expected {empty_custody_bitfield}"
        )


def _validate_aggregation_bitfield(aggregation_bitfield: Bitfield) -> None:
    empty_aggregation_bitfield = b'\x00' * len(aggregation_bitfield)
    if aggregation_bitfield == empty_aggregation_bitfield:
        raise ValidationError(
            "Attestation aggregation bitfield is empty.\n"
            f"\tFound: {aggregation_bitfield}, Expected some bits set."
        )


def _validate_custody_bitfield_from_aggregation_bitfield(committee_size: int,
                                                         aggregation_bitfield: Bitfield,
                                                         custody_bitfield: Bitfield) -> None:
    """
    Ensure that every unset bit in the ``aggregation_bitfield`` is also unset
    in the ``custody_bitfield`` to ensure a canonical representation of information
    between the two sources of data.

    Raise ``ValidationError`` if there is a mismatch.
    """
    for i in range(committee_size):
        if not bitfield.has_voted(aggregation_bitfield, i):
            if bitfield.has_voted(custody_bitfield, i):
                raise ValidationError(
                    "Invalid attestation bitfields:\n"
                    f"\tExpected index {i} to not have custody data because "
                    "they did not participate in this attestation."
                )


def validate_attestation_aggregate_signature(state: BeaconState,
                                             attestation: Attestation,
                                             committee_config: CommitteeConfig) -> None:
    """
    Validate ``aggregate_signature`` field of ``attestation``.
    Raise ``ValidationError`` if it's invalid.

    Note: This is the phase 0 version of `aggregate_signature`` validation.
    All proof of custody bits are assumed to be 0 within the signed data.
    This will change to reflect real proof of custody bits in the Phase 1.
    """
    _validate_custody_bitfield(attestation.custody_bitfield)

    _validate_aggregation_bitfield(attestation.aggregation_bitfield)

    committee = get_crosslink_committee_for_attestation(
        state=state,
        attestation_data=attestation.data,
        committee_config=committee_config,
    )

    _validate_custody_bitfield_from_aggregation_bitfield(
        len(committee),
        attestation.aggregation_bitfield,
        attestation.custody_bitfield,
    )

    participants = get_members_from_bitfield(committee, attestation.aggregation_bitfield)
    custody_bit_1_participants = get_members_from_bitfield(committee, attestation.custody_bitfield)
    custody_bit_0_participants = (i for i in participants if i not in custody_bit_1_participants)

    pubkeys = generate_aggregate_pubkeys_from_indices(
        state.validator_registry,
        custody_bit_0_participants,
        custody_bit_1_participants,
    )

    # TODO: change to tree hashing (hash_tree_root) when we have SSZ
    messages = (
        AttestationDataAndCustodyBit(data=attestation.data, custody_bit=False).root,
        AttestationDataAndCustodyBit(data=attestation.data, custody_bit=True).root,
    )

    domain = get_domain(
        fork=state.fork,
        epoch=slot_to_epoch(attestation.data.slot, committee_config.EPOCH_LENGTH),
        domain_type=SignatureDomain.DOMAIN_ATTESTATION,
    )

    is_valid_signature = bls.verify_multiple(
        pubkeys=pubkeys,
        messages=messages,
        signature=attestation.aggregate_signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            "Attestation aggregate_signature is invalid. "
            "messages={}, custody_bit_0_participants={}, custody_bit_1_participants={} "
            "domain={}".format(
                messages,
                custody_bit_0_participants,
                custody_bit_1_participants,
                domain,
            )
        )


def validate_randao_reveal(randao_reveal: BLSSignature,
                           proposer_pubkey: BLSPubkey,
                           epoch: EpochNumber,
                           fork: Fork) -> None:
    message = epoch.to_bytes(32, byteorder="big")
    domain = get_domain(fork, epoch, SignatureDomain.DOMAIN_RANDAO)

    is_randao_reveal_valid = bls.verify(
        pubkey=proposer_pubkey,
        message=message,
        signature=randao_reveal,
        domain=domain,
    )

    if not is_randao_reveal_valid:
        raise ValidationError(
            f"RANDAO reveal is invalid. "
            f"reveal={randao_reveal}, proposer_pubkey={proposer_pubkey}, message={message}, "
            f"domain={domain}"
        )


#
# Slashable attestation validation
#
def verify_slashable_attestation_signature(state: 'BeaconState',
                                           slashable_attestation: 'SlashableAttestation',
                                           epoch_length: int) -> bool:
    """
    Ensure we have a valid aggregate signature for the ``slashable_attestation``.
    """
    all_indices = slashable_attestation.custody_bit_indices

    pubkeys = generate_aggregate_pubkeys_from_indices(state.validator_registry, *all_indices)

    messages = slashable_attestation.messages

    signature = slashable_attestation.aggregate_signature

    domain = get_domain(
        state.fork,
        slot_to_epoch(slashable_attestation.data.slot, epoch_length),
        SignatureDomain.DOMAIN_ATTESTATION,
    )

    return bls.verify_multiple(
        pubkeys=pubkeys,
        messages=messages,
        signature=signature,
        domain=domain,
    )


def validate_slashable_attestation(state: 'BeaconState',
                                   slashable_attestation: 'SlashableAttestation',
                                   max_indices_per_slashable_vote: int,
                                   epoch_length: int) -> None:
    """
    Verify validity of ``slashable_attestation`` fields.
    Ensure that the ``slashable_attestation`` is properly assembled and contains the signature
    we expect from the validators we expect. Otherwise, return False as
    the ``slashable_attestation`` is invalid.
    """
    _validate_custody_bitfield(slashable_attestation.custody_bitfield)

    if len(slashable_attestation.validator_indices) == 0:
        raise ValidationError(
            "`slashable_attestation.validator_indices` is empty."
        )

    if not slashable_attestation.are_validator_indices_ascending:
        raise ValidationError(
            "`slashable_attestation.validator_indices` "
            f"({slashable_attestation.validator_indices}) "
            "is not ordered in ascending."
        )

    validate_bitfield(
        slashable_attestation.custody_bitfield,
        len(slashable_attestation.validator_indices),
    )

    if len(slashable_attestation.validator_indices) > max_indices_per_slashable_vote:
        raise ValidationError(
            f"`len(slashable_attestation.validator_indices)` "
            f"({len(slashable_attestation.validator_indices)}) greater than"
            f"MAX_INDICES_PER_SLASHABLE_VOTE ({max_indices_per_slashable_vote})"
        )

    if not verify_slashable_attestation_signature(state, slashable_attestation, epoch_length):
        raise ValidationError(
            f"slashable_attestation.signature error"
        )
