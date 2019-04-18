import functools
from typing import (  # noqa: F401
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import (
    BLSPubkey,
    BLSSignature,
)
from eth_utils import (
    encode_hex,
    to_tuple,
    ValidationError,
)
import ssz

from eth.constants import (
    ZERO_HASH32,
)

from py_ecc import bls
from eth2._utils import (
    bitfield,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_crosslink_committee_for_attestation,
    get_members_from_bitfield,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.helpers import (
    get_domain,
    is_double_vote,
    is_surround_vote,
    slot_to_epoch,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestation_data_and_custody_bits import AttestationDataAndCustodyBit
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BaseBeaconBlock, BeaconBlockHeader
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.slashable_attestations import SlashableAttestation
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Bitfield,
    Epoch,
    Slot,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
)

if TYPE_CHECKING:
    from eth_typing import (
        Hash32,
    )


#
# Slot validatation
#
def validate_block_slot(state: BeaconState,
                        block: BaseBeaconBlock) -> None:
    if block.slot != state.slot:
        raise ValidationError(
            f"block.slot ({block.slot}) is not equal to state.slot ({state.slot})"
        )


def validate_block_previous_root(state: BeaconState,
                                 block: BaseBeaconBlock) -> None:
    expected_root = state.latest_block_header.signing_root
    previous_root = block.previous_block_root
    if previous_root != expected_root:
        raise ValidationError(
            f"block.previous_block_root ({encode_hex(previous_root)}) is not equal to "
            f"state.latest_block_header.signing_root ({encode_hex(expected_root)}"
        )


#
# Proposer signature validation
#
def validate_proposer_signature(state: BeaconState,
                                block: BaseBeaconBlock,
                                committee_config: CommitteeConfig) -> None:
    message_hash = block.signing_root

    # Get the public key of proposer
    beacon_proposer_index = get_beacon_proposer_index(
        state,
        state.slot,
        committee_config,
    )
    proposer_pubkey = state.validator_registry[beacon_proposer_index].pubkey
    domain = get_domain(
        state.fork,
        state.current_epoch(committee_config.SLOTS_PER_EPOCH),
        SignatureDomain.DOMAIN_BEACON_BLOCK
    )

    is_valid_signature = bls.verify(
        pubkey=proposer_pubkey,
        message_hash=message_hash,
        signature=block.signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            f"Invalid Proposer Signature on block, beacon_proposer_index={beacon_proposer_index}, "
            f"pubkey={proposer_pubkey}, message_hash={message_hash}, "
            f"block.signature={block.signature}, domain={domain}"
        )


#
# Proposer slashing validation
#
def validate_proposer_slashing(state: BeaconState,
                               proposer_slashing: ProposerSlashing,
                               slots_per_epoch: int) -> None:
    """
    Validate the given ``proposer_slashing``.
    Raise ``ValidationError`` if it's invalid.
    """
    proposer = state.validator_registry[proposer_slashing.proposer_index]

    validate_proposer_slashing_epoch(proposer_slashing, slots_per_epoch)

    validate_proposer_slashing_headers(proposer_slashing)

    validate_proposer_slashing_is_slashed(proposer.slashed)

    validate_block_header_signature(
        header=proposer_slashing.header_1,
        pubkey=proposer.pubkey,
        fork=state.fork,
        slots_per_epoch=slots_per_epoch,
    )

    validate_block_header_signature(
        header=proposer_slashing.header_2,
        pubkey=proposer.pubkey,
        fork=state.fork,
        slots_per_epoch=slots_per_epoch,
    )


def validate_proposer_slashing_epoch(proposer_slashing: ProposerSlashing,
                                     slots_per_epoch: int) -> None:
    epoch_1 = slot_to_epoch(proposer_slashing.header_1.slot, slots_per_epoch)
    epoch_2 = slot_to_epoch(proposer_slashing.header_2.slot, slots_per_epoch)

    if epoch_1 != epoch_2:
        raise ValidationError(
            f"Epoch of proposer_slashing.proposal_1 ({epoch_1}) !="
            f" epoch of proposer_slashing.proposal_2 ({epoch_2})"
        )


def validate_proposer_slashing_headers(proposer_slashing: ProposerSlashing) -> None:
    header_1 = proposer_slashing.header_1
    header_2 = proposer_slashing.header_2
    if header_1 == header_2:
        raise ValidationError(
            f"proposer_slashing.header_1 ({header_1}) == proposer_slashing.header_2 ({header_2})"
        )


def validate_proposer_slashing_is_slashed(slashed: bool) -> None:
    if slashed:
        raise ValidationError(f"proposer.slashed is True")


def validate_block_header_signature(header: BeaconBlockHeader,
                                    pubkey: BLSPubkey,
                                    fork: Fork,
                                    slots_per_epoch: int) -> None:
    header_signature_is_valid = bls.verify(
        pubkey=pubkey,
        message_hash=header.signing_root,
        signature=header.signature,
        domain=get_domain(
            fork,
            slot_to_epoch(header.slot, slots_per_epoch),
            SignatureDomain.DOMAIN_BEACON_BLOCK,
        )
    )
    if not header_signature_is_valid:
        raise ValidationError(
            "Header signature is invalid: "
            f"proposer pubkey: {pubkey}, message_hash: {header.signing_root}, "
            f"signature: {header.signature}"
        )


#
# Attester slashing validation
#
def validate_attester_slashing(state: BeaconState,
                               attester_slashing: AttesterSlashing,
                               max_indices_per_slashable_vote: int,
                               slots_per_epoch: int) -> None:
    slashable_attestation_1 = attester_slashing.slashable_attestation_1
    slashable_attestation_2 = attester_slashing.slashable_attestation_2

    validate_attester_slashing_different_data(slashable_attestation_1, slashable_attestation_2)

    validate_attester_slashing_slashing_conditions(
        slashable_attestation_1,
        slashable_attestation_2,
        slots_per_epoch,
    )

    validate_slashable_attestation(
        state,
        slashable_attestation_1,
        max_indices_per_slashable_vote,
        slots_per_epoch,
    )

    validate_slashable_attestation(
        state,
        slashable_attestation_2,
        max_indices_per_slashable_vote,
        slots_per_epoch,
    )


def validate_attester_slashing_different_data(
        slashable_attestation_1: SlashableAttestation,
        slashable_attestation_2: SlashableAttestation) -> None:
    if slashable_attestation_1.data == slashable_attestation_2.data:
        raise ValidationError(
            "slashable_attestation_1.data "
            f"({slashable_attestation_1.data}) "
            "should not be equal to slashable_attestation_2.data "
            f"({slashable_attestation_2.data})"
        )


def validate_attester_slashing_slashing_conditions(
        slashable_attestation_1: SlashableAttestation,
        slashable_attestation_2: SlashableAttestation,
        slots_per_epoch: int) -> None:
    is_double_vote_slashing = is_double_vote(
        slashable_attestation_1.data,
        slashable_attestation_2.data,
        slots_per_epoch,
    )
    is_surround_vote_slashing = is_surround_vote(
        slashable_attestation_1.data,
        slashable_attestation_2.data,
        slots_per_epoch,
    )
    if not (is_double_vote_slashing or is_surround_vote_slashing):
        raise ValidationError(
            "The `AttesterSlashing` object doesn't meet `is_double_vote` or `is_surround_vote`"
        )


def validate_slashable_indices(slashable_indices: Sequence[ValidatorIndex]) -> None:
    if len(slashable_indices) < 1:
        raise ValidationError(
            "len(slashable_indices) should be greater or equal to 1"
        )


#
# Attestation validation
#
def validate_attestation(state: BeaconState,
                         attestation: Attestation,
                         min_attestation_inclusion_delay: int,
                         slots_per_historical_root: int,
                         committee_config: CommitteeConfig) -> None:
    """
    Validate the given ``attestation``.
    Raise ``ValidationError`` if it's invalid.
    """
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH

    validate_attestation_slot(
        attestation.data,
        state.slot,
        slots_per_epoch,
        min_attestation_inclusion_delay,
        committee_config.GENESIS_SLOT,
    )

    validate_attestation_source_epoch_and_root(
        state,
        attestation.data,
        state.current_epoch(slots_per_epoch),
        slots_per_epoch,
    )

    validate_attestation_previous_crosslink_or_root(
        attestation_data=attestation.data,
        state_latest_crosslink=state.latest_crosslinks[attestation.data.shard],
        slots_per_epoch=slots_per_epoch,
    )

    validate_attestation_crosslink_data_root(attestation.data)

    validate_attestation_aggregate_signature(
        state,
        attestation,
        committee_config,
    )


def validate_attestation_slot(attestation_data: AttestationData,
                              state_slot: Slot,
                              slots_per_epoch: int,
                              min_attestation_inclusion_delay: int,
                              genesis_slot: Slot) -> None:
    """
    Validate ``slot`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if attestation_data.slot < genesis_slot:
        raise ValidationError(
            "Can't submit attestations that are too far in history (or in prehistory):\n"
            f"\tFound attestation slot: {attestation_data.slot}, "
            f"needed greater than or equal to `GENESIS_SLOT` ({genesis_slot})"
        )

    if state_slot > attestation_data.slot + slots_per_epoch:
        raise ValidationError(
            "Attestation slot plus `SLOTS_PER_EPOCH` is too low\n"
            f"\tFound: {attestation_data.slot + slots_per_epoch} "
            f"({attestation_data.slot} + {slots_per_epoch}), "
            f"Needed greater than or equal to: {state_slot}"
        )

    if attestation_data.slot + min_attestation_inclusion_delay > state_slot:
        raise ValidationError(
            "Can't submit attestations too quickly; attestation slot is greater than "
            f"current state slot ({state_slot} minus "
            f"MIN_ATTESTATION_INCLUSION_DELAY ({min_attestation_inclusion_delay}).\n"
            f"\tFound: {attestation_data.slot}, Needed less than or equal to "
            f"({state_slot} - {min_attestation_inclusion_delay})"
        )


def validate_attestation_source_epoch_and_root(state: BeaconState,
                                               attestation_data: AttestationData,
                                               current_epoch: Epoch,
                                               slots_per_epoch: int) -> None:
    """
    Validate ``source_epoch`` and ``source_root`` fields of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if slot_to_epoch(attestation_data.slot, slots_per_epoch) >= current_epoch:
        # Case 1: current epoch attestations
        if attestation_data.source_epoch != state.current_justified_epoch:
            raise ValidationError(
                "Current epoch attestation that "
                "`source_epoch` is not targeting the `state.current_justified_epoch`:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.source_epoch, state.current_justified_epoch)
            )

        if attestation_data.source_root != state.current_justified_root:
            raise ValidationError(
                "Current epoch attestation that "
                "`source_root` is not equal to `state.current_justified_root`:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.source_root, state.current_justified_root)
            )
    else:
        # Case 2: previous epoch attestations
        if attestation_data.source_epoch != state.previous_justified_epoch:
            raise ValidationError(
                "Previous epoch attestation that "
                "`source_epoch`` is not targeting the `state.previous_justified_epoch`:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.source_epoch, state.previous_justified_epoch)
            )

        if attestation_data.source_root != state.previous_justified_root:
            raise ValidationError(
                "Previous epoch attestation that "
                "`source_root` is not equal to `state.previous_justified_root`:\n"
                "\tFound: %s, Expected %s" %
                (attestation_data.source_root, state.previous_justified_root)
            )


def validate_attestation_previous_crosslink_or_root(attestation_data: AttestationData,
                                                    state_latest_crosslink: Crosslink,
                                                    slots_per_epoch: int) -> None:
    """
    Validate that either the attestation ``previous_crosslink`` or ``crosslink_data_root``
    field of ``attestation_data`` is the provided ``latest_crosslink``.
    Raise ``ValidationError`` if it's invalid.
    """
    attestation_creating_crosslink = Crosslink(
        epoch=slot_to_epoch(attestation_data.slot, slots_per_epoch),
        crosslink_data_root=attestation_data.crosslink_data_root,
    )
    acceptable_crosslink_data = {
        # Case 1: Latest crosslink matches the one in the state
        attestation_data.previous_crosslink,
        # Case 2: State has already been updated, state's latest crosslink matches the crosslink
        # the attestation is trying to create
        attestation_creating_crosslink,
    }
    if state_latest_crosslink not in acceptable_crosslink_data:
        raise ValidationError(
            f"State's latests crosslink ({state_latest_crosslink}) doesn't match "
            " case 1: the `attestation_data.previous_crosslink` "
            f"({attestation_data.previous_crosslink.root}) or "
            "`case 2: the crosslink the attestation is trying to create "
            f"({attestation_creating_crosslink})"
        )


def validate_attestation_crosslink_data_root(attestation_data: AttestationData) -> None:
    """
    Validate ``crosslink_data_root`` field of `attestation_data`.
    Raise ``ValidationError`` if it's invalid.

    Note: This is the Phase 0 version of ``crosslink_data_root`` validation.
    This is a built-in stub and will be changed in phase 1.
    """
    if attestation_data.crosslink_data_root != ZERO_HASH32:
        raise ValidationError(
            "Attestation ``crosslink_data_root`` is not ZERO_HASH32.\n"
            "\tFound: %s, Expected %s" %
            (
                attestation_data.crosslink_data_root,
                ZERO_HASH32,
            )
        )


@to_tuple
def get_pubkey_for_indices(validators: Sequence[Validator],
                           indices: Sequence[ValidatorIndex]) -> Iterable[BLSPubkey]:
    for index in indices:
        yield validators[index].pubkey


@to_tuple
def generate_aggregate_pubkeys_from_indices(
        validators: Sequence[Validator],
        *indices: Sequence[Sequence['ValidatorIndex']]) -> Iterable[BLSPubkey]:
    get_pubkeys = functools.partial(get_pubkey_for_indices, validators)
    return map(
        bls.aggregate_pubkeys,
        map(get_pubkeys, indices),
    )


def _validate_custody_bitfield(custody_bitfield: Bitfield) -> None:
    # TODO: to be removed in phase 1.
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
    message_hashes = (
        AttestationDataAndCustodyBit(data=attestation.data, custody_bit=False).root,
        AttestationDataAndCustodyBit(data=attestation.data, custody_bit=True).root,
    )

    domain = get_domain(
        fork=state.fork,
        epoch=slot_to_epoch(attestation.data.slot, committee_config.SLOTS_PER_EPOCH),
        domain_type=SignatureDomain.DOMAIN_ATTESTATION,
    )

    is_valid_signature = bls.verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=attestation.aggregate_signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            "Attestation aggregate_signature is invalid. "
            "message_hashes={}, custody_bit_0_participants={}, custody_bit_1_participants={} "
            "domain={}".format(
                message_hashes,
                custody_bit_0_participants,
                custody_bit_1_participants,
                domain,
            )
        )


def validate_randao_reveal(randao_reveal: BLSSignature,
                           proposer_index: ValidatorIndex,
                           proposer_pubkey: BLSPubkey,
                           epoch: Epoch,
                           fork: Fork) -> None:
    message_hash = ssz.hash_tree_root(epoch, sedes=ssz.sedes.uint64)
    domain = get_domain(fork, epoch, SignatureDomain.DOMAIN_RANDAO)

    is_randao_reveal_valid = bls.verify(
        pubkey=proposer_pubkey,
        message_hash=message_hash,
        signature=randao_reveal,
        domain=domain,
    )

    if not is_randao_reveal_valid:
        raise ValidationError(
            f"RANDAO reveal is invalid. "
            f"proposer_index={proposer_index}, proposer_pubkey={proposer_pubkey}, "
            f"reveal={randao_reveal}, "
            f"message_hash={message_hash}, domain={domain}, epoch={epoch}"
        )


#
# Slashable attestation validation
#
def verify_slashable_attestation_signature(state: BeaconState,
                                           slashable_attestation: SlashableAttestation,
                                           slots_per_epoch: int) -> bool:
    """
    Ensure we have a valid aggregate signature for the ``slashable_attestation``.
    """
    all_indices = slashable_attestation.custody_bit_indices
    pubkeys: Tuple[BLSPubkey, ...] = generate_aggregate_pubkeys_from_indices(
        state.validator_registry,
        *all_indices,
    )
    message_hashes: Tuple[Hash32, ...] = slashable_attestation.message_hashes

    signature = slashable_attestation.aggregate_signature

    domain = get_domain(
        state.fork,
        slot_to_epoch(slashable_attestation.data.slot, slots_per_epoch),
        SignatureDomain.DOMAIN_ATTESTATION,
    )

    # No custody bit 1 indice votes in phase 0, so we only need to process custody bit 0
    # for efficiency.
    # TODO: to be removed in phase 1.
    if len(all_indices[1]) == 0:
        pubkeys = pubkeys[:1]
        message_hashes = message_hashes[:1]

    return bls.verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=signature,
        domain=domain,
    )


def validate_slashable_attestation(state: BeaconState,
                                   slashable_attestation: SlashableAttestation,
                                   max_indices_per_slashable_vote: int,
                                   slots_per_epoch: int) -> None:
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
            f"({len(slashable_attestation.validator_indices)}) greater than "
            f"MAX_INDICES_PER_SLASHABLE_VOTE ({max_indices_per_slashable_vote})"
        )

    if not verify_slashable_attestation_signature(state, slashable_attestation, slots_per_epoch):
        raise ValidationError(
            f"slashable_attestation.signature error"
        )


#
# Voluntary Exit
#
def validate_voluntary_exit(state: BeaconState,
                            voluntary_exit: VoluntaryExit,
                            slots_per_epoch: int,
                            persistent_committee_period: int) -> None:
    validator = state.validator_registry[voluntary_exit.validator_index]
    current_epoch = state.current_epoch(slots_per_epoch)

    validate_voluntary_exit_validator_exit_epoch(validator)

    validate_voluntary_exit_initiated_exit(validator)

    validate_voluntary_exit_epoch(voluntary_exit, current_epoch)

    validate_voluntary_exit_persistent(validator, current_epoch, persistent_committee_period)

    validate_voluntary_exit_signature(state, voluntary_exit, validator)


def validate_voluntary_exit_validator_exit_epoch(validator: Validator) -> None:
    """
    Verify the validator has not yet exited.
    """
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        raise ValidationError(
            f"validator.exit_epoch ({validator.exit_epoch}) should be equal to "
            f"FAR_FUTURE_EPOCH ({FAR_FUTURE_EPOCH})"
        )


def validate_voluntary_exit_initiated_exit(validator: Validator) -> None:
    """
    Verify the validator has not initiated an exit.
    """
    if validator.initiated_exit is True:
        raise ValidationError(
            f"validator.initiated_exit ({validator.initiated_exit}) should be False"
        )


def validate_voluntary_exit_epoch(voluntary_exit: VoluntaryExit,
                                  current_epoch: Epoch) -> None:
    """
    Exits must specify an epoch when they become valid; they are not valid before then.
    """
    if current_epoch < voluntary_exit.epoch:
        raise ValidationError(
            f"voluntary_exit.epoch ({voluntary_exit.epoch}) should be less than or equal to "
            f"current epoch ({current_epoch})"
        )


def validate_voluntary_exit_persistent(validator: Validator,
                                       current_epoch: Epoch,
                                       persistent_committee_period: int) -> None:
    """
    # Must have been in the validator set long enough
    """
    if current_epoch - validator.activation_epoch < persistent_committee_period:
        raise ValidationError(
            "current_epoch - validator.activation_epoch "
            f"({current_epoch} - {validator.activation_epoch}) should be greater than or equal to "
            f"PERSISTENT_COMMITTEE_PERIOD ({persistent_committee_period})"
        )


def validate_voluntary_exit_signature(state: BeaconState,
                                      voluntary_exit: VoluntaryExit,
                                      validator: Validator) -> None:
    """
    Verify signature.
    """
    domain = get_domain(state.fork, voluntary_exit.epoch, SignatureDomain.DOMAIN_VOLUNTARY_EXIT)
    is_valid_signature = bls.verify(
        pubkey=validator.pubkey,
        message_hash=voluntary_exit.signing_root,
        signature=voluntary_exit.signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            f"Invalid VoluntaryExit signature, validator_index={voluntary_exit.validator_index}, "
            f"pubkey={validator.pubkey}, message_hash={voluntary_exit.signing_root},"
            f"signature={voluntary_exit.signature}, domain={domain}"
        )
