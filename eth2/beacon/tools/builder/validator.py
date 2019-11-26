import math
import random
from typing import Dict, Iterable, Sequence, Tuple

from eth_typing import BLSPubkey, BLSSignature, Hash32
from eth_utils import to_tuple
from eth_utils.toolz import keymap as keymapper
from eth_utils.toolz import pipe

from eth2._utils.bitfield import get_empty_bitfield, set_voted
from eth2._utils.bls import Domain, bls
from eth2._utils.hash import hash_eth2
from eth2._utils.merkle.common import MerkleTree, get_merkle_proof
from eth2._utils.merkle.sparse import calc_merkle_tree_from_leaves, get_root
from eth2.beacon.committee_helpers import (
    get_committee_count_at_slot,
    iterate_committees_at_epoch,
    iterate_committees_at_slot,
)
from eth2.beacon.constants import ZERO_SIGNING_ROOT
from eth2.beacon.helpers import (
    compute_domain,
    compute_epoch_at_slot,
    compute_start_slot_at_epoch,
    get_block_root,
    get_block_root_at_slot,
    get_domain,
)
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.state_machines.base import BaseBeaconStateMachine
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BeaconBlockHeader
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.typing import (
    Bitfield,
    CommitteeIndex,
    CommitteeValidatorIndex,
    Epoch,
    Gwei,
    SigningRoot,
    Slot,
    ValidatorIndex,
    default_bitfield,
    default_committee_index,
    default_epoch,
    default_slot,
)
from eth2.configs import CommitteeConfig, Eth2Config


#
# Validator pool utilities
#
def mk_key_pair_from_seed_index(seed_index: int) -> Tuple[BLSPubkey, int]:
    privkey = int.from_bytes(hash_eth2(str(seed_index).encode("utf-8"))[:4], "big")
    pubkey = bls.privtopub(privkey)
    return (pubkey, privkey)


def mk_keymap_of_size(n: int) -> Dict[BLSPubkey, int]:
    keymap = {}
    for i in range(n):
        key_pair = mk_key_pair_from_seed_index(i)
        keymap[key_pair[0]] = key_pair[1]
    return keymap


# TODO(ralexstokes) merge w/ below
def _mk_pending_attestation(
    bitfield: Bitfield = default_bitfield,
    target_root: SigningRoot = ZERO_SIGNING_ROOT,
    target_epoch: Epoch = default_epoch,
    slot: Slot = default_slot,
    committee_index: CommitteeIndex = default_committee_index,
) -> PendingAttestation:
    return PendingAttestation(
        aggregation_bits=bitfield,
        data=AttestationData(
            slot=slot,
            index=committee_index,
            target=Checkpoint(epoch=target_epoch, root=target_root),
        ),
    )


def mk_pending_attestation_from_committee(
    committee_size: int,
    target_epoch: Epoch = default_epoch,
    target_root: SigningRoot = ZERO_SIGNING_ROOT,
    slot: Slot = default_slot,
    committee_index: CommitteeIndex = default_committee_index,
) -> PendingAttestation:
    bitfield = get_empty_bitfield(committee_size)
    for i in range(committee_size):
        bitfield = set_voted(bitfield, i)

    return _mk_pending_attestation(
        bitfield=bitfield,
        target_root=target_root,
        target_epoch=target_epoch,
        slot=slot,
        committee_index=committee_index,
    )


def _mk_some_pending_attestations_with_some_participation_in_epoch(
    state: BeaconState, epoch: Epoch, config: Eth2Config, participation_ratio: float
) -> Iterable[PendingAttestation]:
    block_root = get_block_root(
        state, epoch, config.SLOTS_PER_EPOCH, config.SLOTS_PER_HISTORICAL_ROOT
    )
    for committee, committee_index, slot in iterate_committees_at_epoch(
        state, epoch, CommitteeConfig(config)
    ):
        if not committee:
            continue

        committee_size = len(committee)
        participants_count = math.ceil(participation_ratio * committee_size)
        if not participants_count:
            return tuple()

        yield mk_pending_attestation_from_committee(
            committee_size,
            target_epoch=epoch,
            target_root=block_root,
            slot=Slot(slot),
            committee_index=committee_index,
        )


def mk_all_pending_attestations_with_some_participation_in_epoch(
    state: BeaconState, epoch: Epoch, config: Eth2Config, participation_ratio: float
) -> Iterable[PendingAttestation]:
    return _mk_some_pending_attestations_with_some_participation_in_epoch(
        state, epoch, config, participation_ratio
    )


@to_tuple
def mk_all_pending_attestations_with_full_participation_in_epoch(
    state: BeaconState, epoch: Epoch, config: Eth2Config
) -> Iterable[PendingAttestation]:
    return mk_all_pending_attestations_with_some_participation_in_epoch(
        state, epoch, config, 1.0
    )


#
# Aggregation
#
def verify_votes(
    message_hash: Hash32,
    votes: Iterable[Tuple[ValidatorIndex, BLSSignature, BLSPubkey]],
    domain: Domain,
) -> Tuple[Tuple[BLSSignature, ...], Tuple[ValidatorIndex, ...]]:
    """
    Verify the given votes.
    """
    sigs_with_committee_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, pubkey) in votes
        if bls.verify(
            message_hash=message_hash, pubkey=pubkey, signature=sig, domain=domain
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
    attesting_indices: Sequence[CommitteeValidatorIndex],
) -> Tuple[Bitfield, BLSSignature]:
    """
    Aggregate the votes.
    """
    # Update the bitfield and append the signatures
    sigs = tuple(sigs) + tuple(voting_sigs)
    bitfield = pipe(
        bitfield,
        *(set_voted(index=committee_index) for committee_index in attesting_indices)
    )

    return bitfield, bls.aggregate_signatures(sigs)


#
# Signer
#
def sign_proof_of_possession(deposit_data: DepositData, privkey: int) -> BLSSignature:
    return bls.sign(
        message_hash=deposit_data.signing_root,
        privkey=privkey,
        domain=compute_domain(SignatureDomain.DOMAIN_DEPOSIT),
    )


def sign_transaction(
    *,
    message_hash: Hash32,
    privkey: int,
    state: BeaconState,
    slot: Slot,
    signature_domain: SignatureDomain,
    slots_per_epoch: int
) -> BLSSignature:
    domain = get_domain(
        state,
        signature_domain,
        slots_per_epoch,
        message_epoch=compute_epoch_at_slot(slot, slots_per_epoch),
    )
    return bls.sign(message_hash=message_hash, privkey=privkey, domain=domain)


SAMPLE_HASH_1 = SigningRoot(Hash32(b"\x11" * 32))
SAMPLE_HASH_2 = Hash32(b"\x22" * 32)


def create_block_header_with_signature(
    state: BeaconState,
    body_root: Hash32,
    privkey: int,
    slots_per_epoch: int,
    parent_root: SigningRoot = SAMPLE_HASH_1,
    state_root: Hash32 = SAMPLE_HASH_2,
) -> BeaconBlockHeader:
    block_header = BeaconBlockHeader(
        slot=state.slot,
        parent_root=parent_root,
        state_root=state_root,
        body_root=body_root,
    )
    block_header_signature = sign_transaction(
        message_hash=block_header.signing_root,
        privkey=privkey,
        state=state,
        slot=block_header.slot,
        signature_domain=SignatureDomain.DOMAIN_BEACON_PROPOSER,
        slots_per_epoch=slots_per_epoch,
    )
    return block_header.copy(signature=block_header_signature)


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
    proposer_index: ValidatorIndex,
) -> ProposerSlashing:
    """
    Return a `ProposerSlashing` derived from the given block roots.

    If the header roots do not match, the `ProposerSlashing` is valid.
    If the header roots do match, the `ProposerSlashing` is not valid.
    """
    slots_per_epoch = config.SLOTS_PER_EPOCH

    block_header_1 = create_block_header_with_signature(
        state,
        block_root_1,
        keymap[state.validators[proposer_index].pubkey],
        slots_per_epoch,
    )

    block_header_2 = create_block_header_with_signature(
        state,
        block_root_2,
        keymap[state.validators[proposer_index].pubkey],
        slots_per_epoch,
    )

    return ProposerSlashing(
        proposer_index=proposer_index, header_1=block_header_1, header_2=block_header_2
    )


#
# AttesterSlashing
#
def create_mock_slashable_attestation(
    state: BeaconState,
    config: Eth2Config,
    keymap: Dict[BLSPubkey, int],
    attestation_slot: Slot,
) -> IndexedAttestation:
    """
    Create an `IndexedAttestation` that is signed by one attester.
    """
    attester_index = ValidatorIndex(0)
    committee = (attester_index,)

    # Use genesis block root as `beacon_block_root`, only for tests.
    beacon_block_root = get_block_root_at_slot(
        state, attestation_slot, config.SLOTS_PER_HISTORICAL_ROOT
    )

    # Get `target_root`
    target_root = _get_target_root(state, config, beacon_block_root)
    # Get `source_root`
    source_root = get_block_root_at_slot(
        state,
        compute_start_slot_at_epoch(
            state.current_justified_checkpoint.epoch, config.SLOTS_PER_EPOCH
        ),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    committees_per_slot = get_committee_count_at_slot(
        state,
        Slot(attestation_slot),
        config.MAX_COMMITTEES_PER_SLOT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )
    # Use the first committee
    assert committees_per_slot > 0
    committee_index = CommitteeIndex(0)

    attestation_data = AttestationData(
        slot=attestation_slot,
        index=committee_index,
        beacon_block_root=beacon_block_root,
        source=Checkpoint(
            epoch=state.current_justified_checkpoint.epoch, root=source_root
        ),
        target=Checkpoint(
            epoch=compute_epoch_at_slot(attestation_slot, config.SLOTS_PER_EPOCH),
            root=target_root,
        ),
    )

    message_hash = attestation_data.hash_tree_root
    attesting_indices = _get_mock_attesting_indices(committee, num_voted_attesters=1)

    signature = sign_transaction(
        message_hash=message_hash,
        privkey=keymap[state.validators[attesting_indices[0]].pubkey],
        state=state,
        slot=attestation_slot,
        signature_domain=SignatureDomain.DOMAIN_BEACON_ATTESTER,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
    )
    validator_indices = tuple(committee[i] for i in attesting_indices)

    return IndexedAttestation(
        attesting_indices=validator_indices, data=attestation_data, signature=signature
    )


def create_mock_attester_slashing_is_double_vote(
    state: BeaconState,
    config: Eth2Config,
    keymap: Dict[BLSPubkey, int],
    attestation_epoch: Epoch,
) -> AttesterSlashing:
    attestation_slot_1 = compute_start_slot_at_epoch(
        attestation_epoch, config.SLOTS_PER_EPOCH
    )
    attestation_slot_2 = Slot(attestation_slot_1 + 1)

    slashable_attestation_1 = create_mock_slashable_attestation(
        state, config, keymap, attestation_slot_1
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        state, config, keymap, attestation_slot_2
    )

    return AttesterSlashing(
        attestation_1=slashable_attestation_1, attestation_2=slashable_attestation_2
    )


def create_mock_attester_slashing_is_surround_vote(
    state: BeaconState,
    config: Eth2Config,
    keymap: Dict[BLSPubkey, int],
    attestation_epoch: Epoch,
) -> AttesterSlashing:
    # target_epoch_2 < target_epoch_1
    attestation_slot_2 = compute_start_slot_at_epoch(
        attestation_epoch, config.SLOTS_PER_EPOCH
    )
    attestation_slot_1 = Slot(attestation_slot_2 + config.SLOTS_PER_EPOCH)

    slashable_attestation_1 = create_mock_slashable_attestation(
        state.copy(
            slot=attestation_slot_1, current_justified_epoch=config.GENESIS_EPOCH
        ),
        config,
        keymap,
        attestation_slot_1,
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        state.copy(
            slot=attestation_slot_1,
            current_justified_epoch=config.GENESIS_EPOCH
            + 1,  # source_epoch_1 < source_epoch_2
        ),
        config,
        keymap,
        attestation_slot_2,
    )

    return AttesterSlashing(
        attestation_1=slashable_attestation_1, attestation_2=slashable_attestation_2
    )


#
# Attestation
#
def _get_target_root(
    state: BeaconState, config: Eth2Config, beacon_block_root: SigningRoot
) -> SigningRoot:

    epoch = compute_epoch_at_slot(state.slot, config.SLOTS_PER_EPOCH)
    epoch_start_slot = compute_start_slot_at_epoch(epoch, config.SLOTS_PER_EPOCH)
    if epoch_start_slot == state.slot:
        return beacon_block_root
    else:
        return get_block_root(
            state, epoch, config.SLOTS_PER_EPOCH, config.SLOTS_PER_HISTORICAL_ROOT
        )


def _get_mock_attesting_indices(
    committee: Sequence[ValidatorIndex], num_voted_attesters: int
) -> Tuple[CommitteeValidatorIndex, ...]:
    """
    Get voting indices of the given ``committee``.
    """
    committee_size = len(committee)
    assert num_voted_attesters <= committee_size

    attesting_indices = tuple(
        CommitteeValidatorIndex(i)
        for i in random.sample(range(committee_size), num_voted_attesters)
    )

    return tuple(sorted(attesting_indices))


def _create_mock_signed_attestation(
    state: BeaconState,
    attestation_data: AttestationData,
    attestation_slot: Slot,
    committee: Sequence[ValidatorIndex],
    num_voted_attesters: int,
    keymap: Dict[BLSPubkey, int],
    slots_per_epoch: int,
    is_for_simulation: bool = True,
    attesting_indices: Sequence[CommitteeValidatorIndex] = None,
) -> Attestation:
    """
    Create a mocking attestation of the given ``attestation_data`` slot with ``keymap``.
    """
    message_hash = attestation_data.hash_tree_root

    if is_for_simulation:
        simulation_attesting_indices = _get_mock_attesting_indices(
            committee, num_voted_attesters
        )
        privkeys = tuple(
            keymap[state.validators[committee[committee_index]].pubkey]
            for committee_index in simulation_attesting_indices
        )
    else:
        privkeys = tuple(keymap.values())

    # Use privkeys to sign the attestation
    signatures = [
        sign_transaction(
            message_hash=message_hash,
            privkey=privkey,
            state=state,
            slot=attestation_slot,
            signature_domain=SignatureDomain.DOMAIN_BEACON_ATTESTER,
            slots_per_epoch=slots_per_epoch,
        )
        for privkey in privkeys
    ]

    # aggregate signatures and construct participant bitfield
    aggregation_bits, aggregate_signature = aggregate_votes(
        bitfield=get_empty_bitfield(len(committee)),
        sigs=(),
        voting_sigs=signatures,
        attesting_indices=attesting_indices
        if not is_for_simulation
        else simulation_attesting_indices,
    )

    # create attestation from attestation_data, particpipant_bitfield, and signature
    return Attestation(
        aggregation_bits=aggregation_bits,
        data=attestation_data,
        signature=aggregate_signature,
    )


def create_signed_attestation_at_slot(
    state: BeaconState,
    config: Eth2Config,
    state_machine: BaseBeaconStateMachine,
    attestation_slot: Slot,
    beacon_block_root: SigningRoot,
    validator_privkeys: Dict[ValidatorIndex, int],
    committee: Tuple[ValidatorIndex, ...],
    committee_index: CommitteeIndex,
    attesting_indices: Sequence[CommitteeValidatorIndex],
) -> Attestation:
    """
    Create the attestations of the given ``attestation_slot`` slot with ``validator_privkeys``.
    """
    state_transition = state_machine.state_transition
    state = state_transition.apply_state_transition(state, future_slot=attestation_slot)

    target_epoch = compute_epoch_at_slot(attestation_slot, config.SLOTS_PER_EPOCH)

    target_root = _get_target_root(state, config, beacon_block_root)

    attestation_data = AttestationData(
        slot=attestation_slot,
        index=committee_index,
        beacon_block_root=beacon_block_root,
        source=Checkpoint(
            epoch=state.current_justified_checkpoint.epoch,
            root=state.current_justified_checkpoint.root,
        ),
        target=Checkpoint(root=target_root, epoch=target_epoch),
    )

    return _create_mock_signed_attestation(
        state,
        attestation_data,
        attestation_slot,
        committee,
        len(committee),
        keymapper(lambda index: state.validators[index].pubkey, validator_privkeys),
        config.SLOTS_PER_EPOCH,
        is_for_simulation=False,
        attesting_indices=attesting_indices,
    )


@to_tuple
def create_mock_signed_attestations_at_slot(
    state: BeaconState,
    config: Eth2Config,
    state_machine: BaseBeaconStateMachine,
    attestation_slot: Slot,
    beacon_block_root: SigningRoot,
    keymap: Dict[BLSPubkey, int],
    voted_attesters_ratio: float = 1.0,
) -> Iterable[Attestation]:
    """
    Create the mocking attestations of the given ``attestation_slot`` slot with ``keymap``.
    """
    committees_per_slot = get_committee_count_at_slot(
        state,
        attestation_slot,
        config.MAX_COMMITTEES_PER_SLOT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    # Get `target_root`
    target_root = _get_target_root(state, config, beacon_block_root)
    target_epoch = compute_epoch_at_slot(state.slot, config.SLOTS_PER_EPOCH)

    for committee, committee_index, _ in iterate_committees_at_slot(
        state, attestation_slot, committees_per_slot, CommitteeConfig(config)
    ):
        attestation_data = AttestationData(
            slot=attestation_slot,
            index=CommitteeIndex(committee_index),
            beacon_block_root=beacon_block_root,
            source=Checkpoint(
                epoch=state.current_justified_checkpoint.epoch,
                root=state.current_justified_checkpoint.root,
            ),
            target=Checkpoint(root=target_root, epoch=target_epoch),
        )

        num_voted_attesters = int(len(committee) * voted_attesters_ratio)

        yield _create_mock_signed_attestation(
            state,
            attestation_data,
            attestation_slot,
            committee,
            num_voted_attesters,
            keymap,
            config.SLOTS_PER_EPOCH,
        )


#
# VoluntaryExit
#
def create_mock_voluntary_exit(
    state: BeaconState,
    config: Eth2Config,
    keymap: Dict[BLSPubkey, int],
    validator_index: ValidatorIndex,
    exit_epoch: Epoch = None,
) -> VoluntaryExit:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_epoch = current_epoch if exit_epoch is None else exit_epoch
    voluntary_exit = VoluntaryExit(epoch=target_epoch, validator_index=validator_index)
    return voluntary_exit.copy(
        signature=sign_transaction(
            message_hash=voluntary_exit.signing_root,
            privkey=keymap[state.validators[validator_index].pubkey],
            state=state,
            slot=compute_start_slot_at_epoch(target_epoch, config.SLOTS_PER_EPOCH),
            signature_domain=SignatureDomain.DOMAIN_VOLUNTARY_EXIT,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
        )
    )


#
# Deposit
#
def create_mock_deposit_data(
    *,
    config: Eth2Config,
    pubkey: BLSPubkey,
    privkey: int,
    withdrawal_credentials: Hash32,
    amount: Gwei = None
) -> DepositData:
    if amount is None:
        amount = config.MAX_EFFECTIVE_BALANCE

    data = DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount
    )
    signature = sign_proof_of_possession(deposit_data=data, privkey=privkey)
    return data.copy(signature=signature)


def make_deposit_tree_and_root(
    list_deposit_data: Sequence[DepositData],
) -> Tuple[MerkleTree, Hash32]:
    deposit_data_leaves = [data.hash_tree_root for data in list_deposit_data]
    length_mix_in = len(list_deposit_data).to_bytes(32, byteorder="little")
    tree = calc_merkle_tree_from_leaves(deposit_data_leaves)
    tree_root = get_root(tree)
    tree_root_with_mix_in = hash_eth2(tree_root + length_mix_in)
    return tree, tree_root_with_mix_in


def make_deposit_proof(
    list_deposit_data: Sequence[DepositData],
    deposit_tree: MerkleTree,
    deposit_tree_root: Hash32,
    deposit_index: int,
) -> Tuple[Hash32, ...]:
    length_mix_in = Hash32(len(list_deposit_data).to_bytes(32, byteorder="little"))
    merkle_proof = get_merkle_proof(deposit_tree, deposit_index)
    merkle_proof_with_mix_in = merkle_proof + (length_mix_in,)
    return merkle_proof_with_mix_in
