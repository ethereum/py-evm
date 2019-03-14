import functools
from typing import (  # noqa: F401
    Iterable,
    Sequence,
    Tuple,
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
    get_block_root,
    get_epoch_start_slot,
    get_delayed_activation_exit_epoch,
    get_domain,
    is_double_vote,
    is_surround_vote,
    slot_to_epoch,
)
from eth2.beacon.types.attestations import Attestation  # noqa: F401
from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
from eth2.beacon.types.attestation_data_and_custody_bits import AttestationDataAndCustodyBit
from eth2.beacon.types.attester_slashings import AttesterSlashing  # noqa: F401
from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.forks import Fork  # noqa: F401
from eth2.beacon.types.proposal import Proposal
from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState  # noqa: F401
from eth2.beacon.types.voluntary_exits import VoluntaryExit  # noqa: F401
from eth2.beacon.typing import (
    Bitfield,
    BLSPubkey,
    BLSSignature,
    Epoch,
    Shard,
    Slot,
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
                                beacon_chain_shard_number: Shard,
                                committee_config: CommitteeConfig) -> None:
    block_without_signature_root = block.block_without_signature_root

    # TODO: Replace this with signed_root
    proposal = Proposal(
        state.slot,
        beacon_chain_shard_number,
        block_without_signature_root,
        signature=block.signature,
    )

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
        SignatureDomain.DOMAIN_PROPOSAL
    )

    is_valid_signature = bls.verify(
        pubkey=proposer_pubkey,
        message_hash=proposal.signed_root,
        signature=proposal.signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            f"Invalid Proposer Signature on block, beacon_proposer_index={beacon_proposer_index}, "
            f"pubkey={proposer_pubkey}, message_hash={proposal.signed_root}, "
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

    validate_proposer_slashing_slot(proposer_slashing)

    validate_proposer_slashing_shard(proposer_slashing)

    validate_proposer_slashing_block_root(proposer_slashing)

    validate_proposer_slashing_is_slashed(proposer.slashed)

    validate_proposal_signature(
        proposal=proposer_slashing.proposal_1,
        pubkey=proposer.pubkey,
        fork=state.fork,
        slots_per_epoch=slots_per_epoch,
    )

    validate_proposal_signature(
        proposal=proposer_slashing.proposal_2,
        pubkey=proposer.pubkey,
        fork=state.fork,
        slots_per_epoch=slots_per_epoch,
    )


def validate_proposer_slashing_slot(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_1.slot != proposer_slashing.proposal_2.slot:
        raise ValidationError(
            f"proposer_slashing.proposal_1.slot ({proposer_slashing.proposal_1.slot}) !="
            f" proposer_slashing.proposal_2.slot ({proposer_slashing.proposal_2.slot})"
        )


def validate_proposer_slashing_shard(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_1.shard != proposer_slashing.proposal_2.shard:
        raise ValidationError(
            f"proposer_slashing.proposal_1.shard ({proposer_slashing.proposal_1.shard}) "
            f"!= proposer_slashing.proposal_2.shard"
            f" ({proposer_slashing.proposal_2.shard})"
        )


def validate_proposer_slashing_block_root(proposer_slashing: ProposerSlashing) -> None:
    if proposer_slashing.proposal_1.block_root == proposer_slashing.proposal_2.block_root:
        raise ValidationError(
            "proposer_slashing.proposal_1.block_root "
            f"({proposer_slashing.proposal_1.block_root}) "
            "should not be equal to proposer_slashing.proposal_2.block_root "
            f"({proposer_slashing.proposal_2.block_root})"
        )


def validate_proposer_slashing_is_slashed(slashed: bool) -> None:
    if slashed:
        raise ValidationError(f"proposer.slashed is True")


def validate_proposal_signature(proposal: Proposal,
                                pubkey: BLSPubkey,
                                fork: Fork,
                                slots_per_epoch: int) -> None:
    proposal_signature_is_valid = bls.verify(
        pubkey=pubkey,
        message_hash=proposal.signed_root,  # TODO: use signed_root
        signature=proposal.signature,
        domain=get_domain(
            fork,
            slot_to_epoch(proposal.slot, slots_per_epoch),
            SignatureDomain.DOMAIN_PROPOSAL,
        )
    )
    if not proposal_signature_is_valid:
        raise ValidationError(
            "Proposal signature is invalid: "
            f"proposer pubkey: {pubkey}, message_hash: {proposal.signed_root}, "
            f"signature: {proposal.signature}"
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
                         latest_block_roots_length: int,
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

    validate_attestation_justified_epoch(
        attestation.data,
        state.current_epoch(slots_per_epoch),
        state.previous_justified_epoch,
        state.justified_epoch,
        slots_per_epoch,
    )

    validate_attestation_justified_block_root(
        attestation.data,
        justified_block_root=get_block_root(
            state=state,
            slot=get_epoch_start_slot(
                attestation.data.justified_epoch,
                slots_per_epoch,
            ),
            latest_block_roots_length=latest_block_roots_length,
        ),
    )

    validate_attestation_latest_crosslink_root(
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

    if state_slot >= attestation_data.slot + slots_per_epoch:
        raise ValidationError(
            "Attestation slot plus `SLOTS_PER_EPOCH` is too low; "
            "must exceed the current state:\n"
            f"\tFound: {attestation_data.slot + slots_per_epoch} "
            f"({attestation_data.slot} + {slots_per_epoch}), "
            f"Needed greater than: {state_slot}"
        )

    if attestation_data.slot + min_attestation_inclusion_delay > state_slot:
        raise ValidationError(
            "Can't submit attestations too quickly; attestation slot is greater than "
            f"current state slot ({state_slot} minus "
            f"MIN_ATTESTATION_INCLUSION_DELAY ({min_attestation_inclusion_delay}).\n"
            f"\tFound: {attestation_data.slot}, Needed less than or equal to "
            f"({state_slot} - {min_attestation_inclusion_delay})"
        )


def validate_attestation_justified_epoch(attestation_data: AttestationData,
                                         current_epoch: Epoch,
                                         previous_justified_epoch: Epoch,
                                         justified_epoch: Epoch,
                                         slots_per_epoch: int) -> None:
    """
    Validate ``justified_epoch`` field of ``attestation_data``.
    Raise ``ValidationError`` if it's invalid.
    """
    if slot_to_epoch(attestation_data.slot + 1, slots_per_epoch) >= current_epoch:
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
                                               state_latest_crosslink: CrosslinkRecord,
                                               slots_per_epoch: int) -> None:
    """
    Validate that either the attestation ``latest_crosslink`` or ``crosslink_data_root``
    field of ``attestation_data`` is the provided ``latest_crosslink``.
    Raise ``ValidationError`` if it's invalid.
    """
    attestation_creating_crosslink = CrosslinkRecord(
        epoch=slot_to_epoch(attestation_data.slot, slots_per_epoch),
        crosslink_data_root=attestation_data.crosslink_data_root,
    )
    acceptable_crosslink_data = {
        # Case 1: Latest crosslink matches the one in the state
        attestation_data.latest_crosslink,
        # Case 2: State has already been updated, state's latest crosslink matches the crosslink
        # the attestation is trying to create
        attestation_creating_crosslink,
    }
    if state_latest_crosslink not in acceptable_crosslink_data:
        raise ValidationError(
            f"State's latests crosslink ({state_latest_crosslink}) doesn't match "
            " case 1: the `attestation_data.latest_crosslink` "
            f"({attestation_data.latest_crosslink.root}) or "
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
    message_hash = Hash32(epoch.to_bytes(32, byteorder="little"))
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
def verify_slashable_attestation_signature(state: 'BeaconState',
                                           slashable_attestation: 'SlashableAttestation',
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


def validate_slashable_attestation(state: 'BeaconState',
                                   slashable_attestation: 'SlashableAttestation',
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
def validate_voluntary_exit(state: 'BeaconState',
                            voluntary_exit: 'VoluntaryExit',
                            slots_per_epoch: int,
                            activation_exit_delay: int) -> None:
    validator = state.validator_registry[voluntary_exit.validator_index]
    current_epoch = state.current_epoch(slots_per_epoch)

    validate_voluntary_exit_validator_exit_epoch(
        state,
        validator,
        current_epoch,
        slots_per_epoch=slots_per_epoch,
        activation_exit_delay=activation_exit_delay,
    )

    validate_voluntary_exit_epoch(voluntary_exit, current_epoch)

    validate_voluntary_exit_signature(state, voluntary_exit, validator)


def validate_voluntary_exit_validator_exit_epoch(state: 'BeaconState',
                                                 validator: 'ValidatorRecord',
                                                 current_epoch: Epoch,
                                                 slots_per_epoch: int,
                                                 activation_exit_delay: int) -> None:
    current_epoch = state.current_epoch(slots_per_epoch)

    # Verify the validator has not yet exited
    delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(
        current_epoch,
        activation_exit_delay,
    )
    if validator.exit_epoch <= delayed_activation_exit_epoch:
        raise ValidationError(
            f"validator.exit_epoch ({validator.exit_epoch}) should be greater than "
            f"delayed_activation_exit_epoch ({delayed_activation_exit_epoch})"
        )


def validate_voluntary_exit_epoch(voluntary_exit: 'VoluntaryExit',
                                  current_epoch: Epoch) -> None:
    # Exits must specify an epoch when they become valid; they are not valid before then
    if current_epoch < voluntary_exit.epoch:
        raise ValidationError(
            f"voluntary_exit.epoch ({voluntary_exit.epoch}) should be less than or equal to "
            f"current epoch ({current_epoch})"
        )


def validate_voluntary_exit_signature(state: 'BeaconState',
                                      voluntary_exit: 'VoluntaryExit',
                                      validator: 'ValidatorRecord') -> None:
    domain = get_domain(state.fork, voluntary_exit.epoch, SignatureDomain.DOMAIN_EXIT)
    is_valid_signature = bls.verify(
        pubkey=validator.pubkey,
        message_hash=voluntary_exit.signed_root,
        signature=voluntary_exit.signature,
        domain=domain,
    )

    if not is_valid_signature:
        raise ValidationError(
            f"Invalid VoluntaryExit signature, validator_index={voluntary_exit.validator_index}, "
            f"pubkey={validator.pubkey}, message_hash={voluntary_exit.signed_root},"
            f"signature={voluntary_exit.signature}, domain={domain}"
        )
