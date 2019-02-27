import random

from typing import (
    Dict,
    Iterable,
    Sequence,
    Tuple,
)

from cytoolz import (
    pipe,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from eth2._utils import bls
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
)
from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.exceptions import (
    NoCommitteeAssignment,
)
from eth2.beacon.helpers import (
    get_block_root,
    get_domain,
    get_epoch_start_slot,
    slot_to_epoch,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.proposal_signed_data import ProposalSignedData
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    BLSPubkey,
    BLSSignature,
    Bitfield,
    CommitteeIndex,
    Epoch,
    Shard,
    Slot,
    ValidatorIndex,
)

from .committee_assignment import (
    CommitteeAssignment,
)


#
# Aggregation
#
def verify_votes(
        message: bytes,
        votes: Iterable[Tuple[CommitteeIndex, BLSSignature, BLSPubkey]],
        domain: SignatureDomain
) -> Tuple[Tuple[BLSSignature, ...], Tuple[CommitteeIndex, ...]]:
    """
    Verify the given votes.
    """
    sigs_with_committee_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, public_key)
        in votes
        if bls.verify(message, public_key, sig, domain)
    )
    try:
        sigs, committee_indices = zip(*sigs_with_committee_info)
    except ValueError:
        sigs = tuple()
        committee_indices = tuple()

    return sigs, committee_indices


def aggregate_votes(
        bitfield: Bitfield,
        sigs: Sequence[BLSSignature],
        voting_sigs: Sequence[BLSSignature],
        voting_committee_indices: Sequence[CommitteeIndex]
) -> Tuple[Bitfield, BLSSignature]:
    """
    Aggregate the votes.
    """
    # Update the bitfield and append the signatures
    sigs = tuple(sigs) + tuple(voting_sigs)
    bitfield = pipe(
        bitfield,
        *(
            set_voted(index=committee_index)
            for committee_index in voting_committee_indices
        )
    )

    return bitfield, bls.aggregate_signatures(sigs)


#
# Signer
#
def sign_proof_of_possession(deposit_input: DepositInput,
                             privkey: int,
                             fork: Fork,
                             slot: Slot,
                             slots_per_epoch: int) -> BLSSignature:
    domain = get_domain(
        fork,
        slot_to_epoch(slot, slots_per_epoch),
        SignatureDomain.DOMAIN_DEPOSIT,
    )
    return bls.sign(
        message=deposit_input.root,
        privkey=privkey,
        domain=domain,
    )


def sign_transaction(*,
                     message: bytes,
                     privkey: int,
                     fork: Fork,
                     slot: Slot,
                     signature_domain: SignatureDomain,
                     slots_per_epoch: int) -> BLSSignature:
    domain = get_domain(
        fork,
        slot_to_epoch(slot, slots_per_epoch),
        signature_domain,
    )
    return bls.sign(
        message=message,
        privkey=privkey,
        domain=domain,
    )

#
#
# Only for test/simulation
#
#


#
# ProposerSlashing
#
def create_proposal_data_and_signature(
        state: BeaconState,
        block_root: Hash32,
        privkey: int,
        slots_per_epoch: int,
        beacon_chain_shard_number: Shard)-> Tuple[ProposalSignedData, BLSSignature]:
    proposal_data = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        block_root,
    )
    proposal_signature = sign_transaction(
        message=proposal_data.root,
        privkey=privkey,
        fork=state.fork,
        slot=proposal_data.slot,
        signature_domain=SignatureDomain.DOMAIN_PROPOSAL,
        slots_per_epoch=slots_per_epoch,
    )
    return proposal_data, proposal_signature


def create_mock_proposer_slashing_at_block(state: BeaconState,
                                           config: BeaconConfig,
                                           keymap: Dict[BLSPubkey, int],
                                           block_root_1: Hash32,
                                           block_root_2: Hash32,
                                           proposer_index: ValidatorIndex)-> ProposerSlashing:
    slots_per_epoch = config.SLOTS_PER_EPOCH
    beacon_chain_shard_number = config.BEACON_CHAIN_SHARD_NUMBER

    proposal_data_1, proposal_signature_1 = create_proposal_data_and_signature(
        state,
        block_root_1,
        keymap[state.validator_registry[proposer_index].pubkey],
        slots_per_epoch,
        beacon_chain_shard_number,
    )

    proposal_data_2, proposal_signature_2 = create_proposal_data_and_signature(
        state,
        block_root_2,
        keymap[state.validator_registry[proposer_index].pubkey],
        slots_per_epoch,
        beacon_chain_shard_number,
    )

    return ProposerSlashing(
        proposer_index=proposer_index,
        proposal_data_1=proposal_data_1,
        proposal_data_2=proposal_data_2,
        proposal_signature_1=proposal_signature_1,
        proposal_signature_2=proposal_signature_2,
    )


#
# Attestation
#
def _get_mock_message_and_voting_committee_indices(
        attestation_data: AttestationData,
        committee: Sequence[ValidatorIndex],
        num_voted_attesters: int) -> Tuple[Hash32, Tuple[CommitteeIndex, ...]]:
    """
    Get ``message`` and voting indices of the given ``committee``.
    """
    message = AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=False
    ).root

    committee_size = len(committee)
    assert num_voted_attesters <= committee_size

    # Index in committee
    voting_committee_indices = tuple(
        CommitteeIndex(i) for i in random.sample(range(committee_size), num_voted_attesters)
    )

    return message, voting_committee_indices


def create_mock_signed_attestation(state: BeaconState,
                                   attestation_data: AttestationData,
                                   committee: Sequence[ValidatorIndex],
                                   num_voted_attesters: int,
                                   keymap: Dict[BLSPubkey, int],
                                   slots_per_epoch: int) -> Attestation:
    """
    Create a mocking attestation of the given ``attestation_data`` slot with ``keymap``.
    """
    message, voting_committee_indices = _get_mock_message_and_voting_committee_indices(
        attestation_data,
        committee,
        num_voted_attesters,
    )

    # Use privkeys to sign the attestation
    signatures = [
        sign_transaction(
            message=message,
            privkey=keymap[
                state.validator_registry[
                    committee[committee_index]
                ].pubkey
            ],
            fork=state.fork,
            slot=attestation_data.slot,
            signature_domain=SignatureDomain.DOMAIN_ATTESTATION,
            slots_per_epoch=slots_per_epoch,
        )
        for committee_index in voting_committee_indices
    ]

    # aggregate signatures and construct participant bitfield
    aggregation_bitfield, aggregate_signature = aggregate_votes(
        bitfield=get_empty_bitfield(len(committee)),
        sigs=(),
        voting_sigs=signatures,
        voting_committee_indices=voting_committee_indices,
    )

    # create attestation from attestation_data, particpipant_bitfield, and signature
    return Attestation(
        data=attestation_data,
        aggregation_bitfield=aggregation_bitfield,
        custody_bitfield=Bitfield(b'\x00' * len(aggregation_bitfield)),
        aggregate_signature=aggregate_signature,
    )


@to_tuple
def create_mock_signed_attestations_at_slot(
        state: BeaconState,
        config: BeaconConfig,
        attestation_slot: Slot,
        beacon_block_root: Hash32,
        keymap: Dict[BLSPubkey, int],
        voted_attesters_ratio: float=1.0) -> Iterable[Attestation]:
    """
    Create the mocking attestations of the given ``attestation_slot`` slot with ``keymap``.
    """
    slots_per_epoch = config.SLOTS_PER_EPOCH

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        # To avoid the epoch boundary cases
        state.copy(
            slot=state.slot + 1,
        ),
        attestation_slot,
        CommitteeConfig(config),
    )

    # Get `epoch_boundary_root`
    epoch_start_slot = get_epoch_start_slot(
        slot_to_epoch(state.slot, slots_per_epoch),
        slots_per_epoch,
    )
    if epoch_start_slot == state.slot:
        epoch_boundary_root = beacon_block_root
    else:
        epoch_boundary_root = get_block_root(
            state,
            epoch_start_slot,
            config.LATEST_BLOCK_ROOTS_LENGTH,
        )

    # Get `justified_block_root`
    justified_block_root = get_block_root(
        state,
        get_epoch_start_slot(state.justified_epoch, slots_per_epoch),
        config.LATEST_BLOCK_ROOTS_LENGTH,
    )

    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee

        num_voted_attesters = int(len(committee) * voted_attesters_ratio)
        latest_crosslink_root = state.latest_crosslinks[shard].shard_block_root

        attestation_data = AttestationData(
            slot=attestation_slot,
            shard=shard,
            beacon_block_root=beacon_block_root,
            epoch_boundary_root=epoch_boundary_root,
            shard_block_root=ZERO_HASH32,
            latest_crosslink_root=latest_crosslink_root,
            justified_epoch=state.justified_epoch,
            justified_block_root=justified_block_root,
        )

        yield create_mock_signed_attestation(
            state,
            attestation_data,
            committee,
            num_voted_attesters,
            keymap,
            config.SLOTS_PER_EPOCH,
        )


#
#
# Validator guide
#
#


#
# Lookahead
#
def get_committee_assignment(
        state: BeaconState,
        config: BeaconConfig,
        epoch: Epoch,
        validator_index: ValidatorIndex,
        registry_change: bool=False
) -> CommitteeAssignment:
    """
    Return the ``CommitteeAssignment`` in the ``epoch`` for ``validator_index``
    and ``registry_change``.
    ``CommitteeAssignment.committee`` is the tuple array of validators in the committee
    ``CommitteeAssignment.shard`` is the shard to which the committee is assigned
    ``CommitteeAssignment.slot`` is the slot at which the committee is assigned
    ``CommitteeAssignment.is_proposer`` is a bool signalling if the validator is expected to
        propose a beacon block at the assigned slot.
    """
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    next_epoch = current_epoch + 1

    if previous_epoch > epoch:
        raise ValidationError(
            f"The given epoch ({epoch}) is less than previous epoch ({previous_epoch})"
        )

    if epoch > next_epoch:
        raise ValidationError(
            f"The given epoch ({epoch}) is greater than next epoch ({previous_epoch})"
        )

    epoch_start_slot = get_epoch_start_slot(epoch, config.SLOTS_PER_EPOCH)

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        crosslink_committees = get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
            registry_change=registry_change,
        )
        selected_committees = [
            committee
            for committee in crosslink_committees
            if validator_index in committee[0]
        ]
        if len(selected_committees) > 0:
            validators = selected_committees[0][0]
            shard = selected_committees[0][1]
            first_committee_at_slot = crosslink_committees[0][0]  # List[ValidatorIndex]
            is_proposer = first_committee_at_slot[
                slot % len(first_committee_at_slot)
            ] == validator_index

            return CommitteeAssignment(validators, shard, Slot(slot), is_proposer)

    raise NoCommitteeAssignment
