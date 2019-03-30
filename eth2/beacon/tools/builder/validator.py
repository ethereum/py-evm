import random
import time

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
    BLSPubkey,
    BLSSignature,
    Hash32,
)
from eth_utils import (
    to_tuple,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from py_ecc import bls

from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.constants import (
    ZERO_TIMESTAMP,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_crosslink_committees_at_slot,
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
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.proposal import Proposal
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.slashable_attestations import SlashableAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.typing import (
    Bitfield,
    CommitteeIndex,
    Epoch,
    Gwei,
    Shard,
    Slot,
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_epoch_within_previous_and_next,
)

from .committee_assignment import (
    CommitteeAssignment,
)


#
# Aggregation
#
def verify_votes(
        message_hash: Hash32,
        votes: Iterable[Tuple[CommitteeIndex, BLSSignature, BLSPubkey]],
        domain: SignatureDomain
) -> Tuple[Tuple[BLSSignature, ...], Tuple[CommitteeIndex, ...]]:
    """
    Verify the given votes.
    """
    sigs_with_committee_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, pubkey)
        in votes
        if bls.verify(
            message_hash=message_hash,
            pubkey=pubkey,
            signature=sig,
            domain=domain,
        )
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
        message_hash=deposit_input.root,
        privkey=privkey,
        domain=domain,
    )


def sign_transaction(*,
                     message_hash: Hash32,
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
        message_hash=message_hash,
        privkey=privkey,
        domain=domain,
    )


def create_proposal_data_and_signature(
        state: BeaconState,
        block_root: Hash32,
        privkey: int,
        slots_per_epoch: int,
        beacon_chain_shard_number: Shard)-> Proposal:
    proposal = Proposal(
        state.slot,
        beacon_chain_shard_number,
        block_root,
    )
    proposal_signature = sign_transaction(
        message_hash=proposal.signed_root,
        privkey=privkey,
        fork=state.fork,
        slot=proposal.slot,
        signature_domain=SignatureDomain.DOMAIN_BEACON_BLOCK,
        slots_per_epoch=slots_per_epoch,
    )
    proposal = proposal.copy(signature=proposal_signature)
    return proposal


#
#
# Only for test/simulation
#
#


#
# ProposerSlashing
#
def create_mock_proposer_slashing_at_block(
        state: BeaconState,
        config: Eth2Config,
        keymap: Dict[BLSPubkey, int],
        block_root_1: Hash32,
        block_root_2: Hash32,
        proposer_index: ValidatorIndex) -> ProposerSlashing:
    slots_per_epoch = config.SLOTS_PER_EPOCH
    beacon_chain_shard_number = config.BEACON_CHAIN_SHARD_NUMBER

    proposal_1 = create_proposal_data_and_signature(
        state,
        block_root_1,
        keymap[state.validator_registry[proposer_index].pubkey],
        slots_per_epoch,
        beacon_chain_shard_number,
    )

    proposal_2 = create_proposal_data_and_signature(
        state,
        block_root_2,
        keymap[state.validator_registry[proposer_index].pubkey],
        slots_per_epoch,
        beacon_chain_shard_number,
    )

    return ProposerSlashing(
        proposer_index=proposer_index,
        proposal_1=proposal_1,
        proposal_2=proposal_2,
    )


#
# AttesterSlashing
#
def create_mock_slashable_attestation(state: BeaconState,
                                      config: Eth2Config,
                                      keymap: Dict[BLSPubkey, int],
                                      attestation_slot: Slot) -> SlashableAttestation:
    """
    Create `SlashableAttestation` that is signed by one attester.
    """
    attester_index = ValidatorIndex(0)
    committee = (attester_index,)
    shard = Shard(0)

    # Use genesis block root as `beacon_block_root`, only for tests.
    beacon_block_root = get_block_root(
        state,
        config.GENESIS_SLOT,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    # Get `epoch_boundary_root`
    epoch_boundary_root = _get_epoch_boundary_root(state, config, beacon_block_root)
    # Get `justified_block_root`
    justified_block_root = get_block_root(
        state,
        get_epoch_start_slot(state.justified_epoch, config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    latest_crosslink = state.latest_crosslinks[shard]

    attestation_data = attestation_data = AttestationData(
        slot=attestation_slot,
        shard=shard,
        beacon_block_root=beacon_block_root,
        epoch_boundary_root=epoch_boundary_root,
        crosslink_data_root=ZERO_HASH32,
        latest_crosslink=latest_crosslink,
        justified_epoch=state.justified_epoch,
        justified_block_root=justified_block_root,
    )

    message_hash, voting_committee_indices = _get_mock_message_and_voting_committee_indices(
        attestation_data,
        committee,
        num_voted_attesters=1,
    )

    signature = sign_transaction(
        message_hash=message_hash,
        privkey=keymap[
            state.validator_registry[
                voting_committee_indices[0]
            ].pubkey
        ],
        fork=state.fork,
        slot=attestation_slot,
        signature_domain=SignatureDomain.DOMAIN_ATTESTATION,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
    )
    validator_indices = tuple(committee[i] for i in voting_committee_indices)

    return SlashableAttestation(
        validator_indices=sorted(validator_indices),
        data=attestation_data,
        custody_bitfield=get_empty_bitfield(len(voting_committee_indices)),
        aggregate_signature=signature,
    )


def create_mock_attester_slashing_is_double_vote(
        state: BeaconState,
        config: Eth2Config,
        keymap: Dict[BLSPubkey, int],
        attestation_epoch: Epoch) -> AttesterSlashing:
    attestation_slot_1 = get_epoch_start_slot(attestation_epoch, config.SLOTS_PER_EPOCH)
    attestation_slot_2 = Slot(attestation_slot_1 + 1)

    slashable_attestation_1 = create_mock_slashable_attestation(
        state,
        config,
        keymap,
        attestation_slot_1,
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        state,
        config,
        keymap,
        attestation_slot_2,
    )

    return AttesterSlashing(
        slashable_attestation_1=slashable_attestation_1,
        slashable_attestation_2=slashable_attestation_2,
    )


def create_mock_attester_slashing_is_surround_vote(
        state: BeaconState,
        config: Eth2Config,
        keymap: Dict[BLSPubkey, int],
        attestation_epoch: Epoch) -> AttesterSlashing:
    # target_epoch_2 < target_epoch_1
    attestation_slot_2 = get_epoch_start_slot(attestation_epoch, config.SLOTS_PER_EPOCH)
    attestation_slot_1 = Slot(attestation_slot_2 + config.SLOTS_PER_EPOCH)

    slashable_attestation_1 = create_mock_slashable_attestation(
        state.copy(
            slot=attestation_slot_1,
            justified_epoch=config.GENESIS_EPOCH,
        ),
        config,
        keymap,
        attestation_slot_1,
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        state.copy(
            slot=attestation_slot_1,
            justified_epoch=config.GENESIS_EPOCH + 1,  # source_epoch_1 < source_epoch_2
        ),
        config,
        keymap,
        attestation_slot_2,
    )

    return AttesterSlashing(
        slashable_attestation_1=slashable_attestation_1,
        slashable_attestation_2=slashable_attestation_2,
    )


#
# Attestation
#
def _get_epoch_boundary_root(state: BeaconState,
                             config: Eth2Config,
                             beacon_block_root: Hash32) -> Hash32:
    epoch_start_slot = get_epoch_start_slot(
        slot_to_epoch(state.slot, config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_EPOCH,
    )
    if epoch_start_slot == state.slot:
        return beacon_block_root
    else:
        return get_block_root(
            state,
            epoch_start_slot,
            config.SLOTS_PER_HISTORICAL_ROOT,
        )


def _get_mock_message_and_voting_committee_indices(
        attestation_data: AttestationData,
        committee: Sequence[ValidatorIndex],
        num_voted_attesters: int) -> Tuple[Hash32, Tuple[CommitteeIndex, ...]]:
    """
    Get ``message_hash`` and voting indices of the given ``committee``.
    """
    message_hash = AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=False
    ).root

    committee_size = len(committee)
    assert num_voted_attesters <= committee_size

    # Index in committee
    voting_committee_indices = tuple(
        CommitteeIndex(i) for i in random.sample(range(committee_size), num_voted_attesters)
    )

    return message_hash, voting_committee_indices


def create_mock_signed_attestation(state: BeaconState,
                                   attestation_data: AttestationData,
                                   committee: Sequence[ValidatorIndex],
                                   num_voted_attesters: int,
                                   keymap: Dict[BLSPubkey, int],
                                   slots_per_epoch: int) -> Attestation:
    """
    Create a mocking attestation of the given ``attestation_data`` slot with ``keymap``.
    """
    message_hash, voting_committee_indices = _get_mock_message_and_voting_committee_indices(
        attestation_data,
        committee,
        num_voted_attesters,
    )

    # Use privkeys to sign the attestation
    signatures = [
        sign_transaction(
            message_hash=message_hash,
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
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=Bitfield(b'\x00' * len(aggregation_bitfield)),
        aggregate_signature=aggregate_signature,
    )


@to_tuple
def create_mock_signed_attestations_at_slot(
        state: BeaconState,
        config: Eth2Config,
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
    epoch_boundary_root = _get_epoch_boundary_root(state, config, beacon_block_root)

    # Get `justified_block_root`
    justified_block_root = get_block_root(
        state,
        get_epoch_start_slot(state.justified_epoch, slots_per_epoch),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee

        num_voted_attesters = int(len(committee) * voted_attesters_ratio)
        latest_crosslink = state.latest_crosslinks[shard]

        attestation_data = AttestationData(
            slot=attestation_slot,
            shard=shard,
            beacon_block_root=beacon_block_root,
            epoch_boundary_root=epoch_boundary_root,
            crosslink_data_root=ZERO_HASH32,
            latest_crosslink=latest_crosslink,
            justified_epoch=state.justified_epoch,
            justified_block_root=justified_block_root,
        )

        num_voted_attesters = int(len(committee) * voted_attesters_ratio)

        yield create_mock_signed_attestation(
            state,
            attestation_data,
            committee,
            num_voted_attesters,
            keymap,
            config.SLOTS_PER_EPOCH,
        )


#
# VoluntaryExit
#
def create_mock_voluntary_exit(state: BeaconState,
                               config: Eth2Config,
                               keymap: Dict[BLSPubkey, int],
                               validator_index: ValidatorIndex,
                               exit_epoch: Epoch=None) -> VoluntaryExit:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    voluntary_exit = VoluntaryExit(
        epoch=state.current_epoch(config.SLOTS_PER_EPOCH) if exit_epoch is None else exit_epoch,
        validator_index=validator_index,
    )
    return voluntary_exit.copy(
        signature=sign_transaction(
            message_hash=voluntary_exit.signed_root,
            privkey=keymap[state.validator_registry[validator_index].pubkey],
            fork=state.fork,
            slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH),
            signature_domain=SignatureDomain.DOMAIN_VOLUNTARY_EXIT,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
        )
    )


#
# Deposit
#
def create_deposit_data(*,
                        config: Eth2Config,
                        pubkey: BLSPubkey,
                        privkey: int,
                        withdrawal_credentials: Hash32,
                        fork: Fork,
                        deposit_timestamp: Timestamp,
                        amount: Gwei=None) -> DepositData:
    if amount is None:
        amount = config.MAX_DEPOSIT_AMOUNT

    return DepositData(
        deposit_input=DepositInput(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            proof_of_possession=sign_proof_of_possession(
                deposit_input=DepositInput(
                    pubkey=pubkey,
                    withdrawal_credentials=withdrawal_credentials,
                ),
                privkey=privkey,
                fork=fork,
                slot=config.GENESIS_SLOT,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
            ),
        ),
        amount=amount,
        timestamp=deposit_timestamp,
    )


def create_mock_deposit_data(*,
                             config: Eth2Config,
                             pubkeys: Sequence[BLSPubkey],
                             keymap: Dict[BLSPubkey, int],
                             validator_index: ValidatorIndex,
                             withdrawal_credentials: Hash32,
                             fork: Fork,
                             deposit_timestamp: Timestamp=ZERO_TIMESTAMP) -> DepositData:
    if deposit_timestamp is None:
        deposit_timestamp = Timestamp(int(time.time()))

    return create_deposit_data(
        config=config,
        pubkey=pubkeys[validator_index],
        privkey=keymap[pubkeys[validator_index]],
        withdrawal_credentials=withdrawal_credentials,
        fork=fork,
        deposit_timestamp=deposit_timestamp,
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
        config: Eth2Config,
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
    next_epoch = Epoch(current_epoch + 1)

    validate_epoch_within_previous_and_next(epoch, previous_epoch, next_epoch)

    epoch_start_slot = get_epoch_start_slot(epoch, config.SLOTS_PER_EPOCH)

    committee_config = CommitteeConfig(config)

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        crosslink_committees = get_crosslink_committees_at_slot(
            state,
            slot,
            committee_config,
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
            is_proposer = validator_index == get_beacon_proposer_index(
                state,
                Slot(slot),
                committee_config,
                registry_change=registry_change,
            )

            return CommitteeAssignment(validators, shard, Slot(slot), is_proposer)

    raise NoCommitteeAssignment
