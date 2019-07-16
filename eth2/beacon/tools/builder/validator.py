import math
import random

from typing import (
    Dict,
    Iterable,
    Sequence,
    Tuple,
)

from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    pipe,
    keymap as keymapper,
)
from eth2._utils.bls import bls

from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.signature_domain import (
    SignatureDomain,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committee,
    get_epoch_committee_count,
    get_epoch_start_shard,
    get_shard_delta,
)
from eth2.beacon.helpers import (
    bls_domain,
    get_block_root_at_slot,
    get_block_root,
    get_domain,
    get_epoch_start_slot,
    slot_to_epoch,
    get_active_validator_indices,
)
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BeaconBlockHeader
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.typing import (
    Bitfield,
    Epoch,
    Gwei,
    Shard,
    Slot,
    ValidatorIndex,
    default_bitfield,
    default_epoch,
    default_shard,
)
from eth2.beacon.state_machines.base import (
    BaseBeaconStateMachine,
)


# TODO(ralexstokes) merge w/ below
def _mk_pending_attestation(bitfield: Bitfield=default_bitfield,
                            target_root: Hash32=ZERO_HASH32,
                            target_epoch: Epoch=default_epoch,
                            shard: Shard=default_shard,
                            start_epoch: Epoch=default_epoch,
                            parent_root: Hash32=ZERO_HASH32,
                            data_root: Hash32=ZERO_HASH32) -> PendingAttestation:
    return PendingAttestation(
        aggregation_bitfield=bitfield,
        data=AttestationData(
            target_epoch=target_epoch,
            target_root=target_root,
            crosslink=Crosslink(
                shard=shard,
                parent_root=parent_root,
                start_epoch=start_epoch,
                end_epoch=target_epoch,
                data_root=data_root,
            )
        ),
    )


def mk_pending_attestation_from_committee(parent: Crosslink,
                                          committee_size: int,
                                          shard: Shard,
                                          target_epoch: Epoch=default_epoch,
                                          target_root: Hash32=ZERO_HASH32,
                                          data_root: Hash32=ZERO_HASH32) -> PendingAttestation:
    bitfield = get_empty_bitfield(committee_size)
    for i in range(committee_size):
        bitfield = set_voted(bitfield, i)

    return _mk_pending_attestation(
        bitfield=bitfield,
        target_root=target_root,
        target_epoch=target_epoch,
        shard=shard,
        start_epoch=parent.end_epoch,
        parent_root=parent.root,
        data_root=data_root,
    )


def _mk_some_pending_attestations_with_some_participation_in_epoch(
        state: BeaconState,
        epoch: Epoch,
        config: Eth2Config,
        participation_ratio: float,
        number_of_shards_to_check: int) -> Iterable[PendingAttestation]:
    block_root = get_block_root(
        state,
        epoch,
        config.SLOTS_PER_EPOCH,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    epoch_start_shard = get_epoch_start_shard(
        state,
        epoch,
        CommitteeConfig(config),
    )

    if epoch == state.current_epoch(config.SLOTS_PER_EPOCH):
        parent_crosslinks = state.current_crosslinks
    else:
        parent_crosslinks = state.previous_crosslinks

    for shard in range(epoch_start_shard, epoch_start_shard + number_of_shards_to_check):
        shard = Shard(shard % config.SHARD_COUNT)
        crosslink_committee = get_crosslink_committee(
            state,
            epoch,
            shard,
            CommitteeConfig(config),
        )
        if not crosslink_committee:
            continue

        participants_count = math.ceil(participation_ratio * len(crosslink_committee))
        if not participants_count:
            return tuple()

        yield mk_pending_attestation_from_committee(
            parent_crosslinks[shard],
            participants_count,
            shard,
            target_epoch=epoch,
            target_root=block_root,
        )


def mk_all_pending_attestations_with_some_participation_in_epoch(
        state: BeaconState,
        epoch: Epoch,
        config: Eth2Config,
        participation_ratio: float) -> Iterable[PendingAttestation]:
    return _mk_some_pending_attestations_with_some_participation_in_epoch(
        state,
        epoch,
        config,
        participation_ratio,
        get_shard_delta(
            state,
            epoch,
            CommitteeConfig(config),
        ),
    )


@to_tuple
def mk_all_pending_attestations_with_full_participation_in_epoch(
        state: BeaconState,
        epoch: Epoch,
        config: Eth2Config) -> Iterable[PendingAttestation]:
    return mk_all_pending_attestations_with_some_participation_in_epoch(
        state,
        epoch,
        config,
        1.0,
    )


#
# Aggregation
#
def verify_votes(
        message_hash: Hash32,
        votes: Iterable[Tuple[ValidatorIndex, BLSSignature, BLSPubkey]],
        domain: SignatureDomain) -> Tuple[Tuple[BLSSignature, ...], Tuple[ValidatorIndex, ...]]:
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
        attesting_indices: Sequence[ValidatorIndex]
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
            for committee_index in attesting_indices
        )
    )

    return bitfield, bls.aggregate_signatures(sigs)


#
# Signer
#
def sign_proof_of_possession(deposit_data: DepositData,
                             privkey: int) -> BLSSignature:
    return bls.sign(
        message_hash=deposit_data.signing_root,
        privkey=privkey,
        domain=bls_domain(SignatureDomain.DOMAIN_DEPOSIT),
    )


def sign_transaction(*,
                     message_hash: Hash32,
                     privkey: int,
                     state: BeaconState,
                     slot: Slot,
                     signature_domain: SignatureDomain,
                     slots_per_epoch: int) -> BLSSignature:
    domain = get_domain(
        state,
        signature_domain,
        slots_per_epoch,
        message_epoch=slot_to_epoch(slot, slots_per_epoch),
    )
    return bls.sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=domain,
    )


SAMPLE_HASH_1 = Hash32(b'\x11' * 32)
SAMPLE_HASH_2 = Hash32(b'\x22' * 32)


def create_block_header_with_signature(
        state: BeaconState,
        body_root: Hash32,
        privkey: int,
        slots_per_epoch: int,
        parent_root: Hash32=SAMPLE_HASH_1,
        state_root: Hash32=SAMPLE_HASH_2)-> BeaconBlockHeader:
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
        proposer_index: ValidatorIndex) -> ProposerSlashing:
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
        proposer_index=proposer_index,
        header_1=block_header_1,
        header_2=block_header_2,
    )


#
# AttesterSlashing
#
def create_mock_slashable_attestation(state: BeaconState,
                                      config: Eth2Config,
                                      keymap: Dict[BLSPubkey, int],
                                      attestation_slot: Slot) -> IndexedAttestation:
    """
    Create an `IndexedAttestation` that is signed by one attester.
    """
    attester_index = ValidatorIndex(0)
    committee = (attester_index,)
    shard = Shard(0)

    # Use genesis block root as `beacon_block_root`, only for tests.
    beacon_block_root = get_block_root_at_slot(
        state,
        attestation_slot,
        config.SLOTS_PER_HISTORICAL_ROOT,
    )

    # Get `target_root`
    target_root = _get_target_root(state, config, beacon_block_root)
    # Get `source_root`
    source_root = get_block_root_at_slot(
        state,
        get_epoch_start_slot(state.current_justified_epoch, config.SLOTS_PER_EPOCH),
        config.SLOTS_PER_HISTORICAL_ROOT,
    )
    previous_crosslink = state.current_crosslinks[shard]

    attestation_data = AttestationData(
        beacon_block_root=beacon_block_root,
        source_epoch=state.current_justified_epoch,
        source_root=source_root,
        target_epoch=slot_to_epoch(
            attestation_slot,
            config.SLOTS_PER_EPOCH,
        ),
        target_root=target_root,
        crosslink=previous_crosslink,
    )

    message_hash, attesting_indices = _get_mock_message_and_attesting_indices(
        attestation_data,
        committee,
        num_voted_attesters=1,
    )

    signature = sign_transaction(
        message_hash=message_hash,
        privkey=keymap[
            state.validators[
                attesting_indices[0]
            ].pubkey
        ],
        state=state,
        slot=attestation_slot,
        signature_domain=SignatureDomain.DOMAIN_ATTESTATION,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
    )
    validator_indices = tuple(committee[i] for i in attesting_indices)

    return IndexedAttestation(
        custody_bit_0_indices=validator_indices,
        custody_bit_1_indices=tuple(),
        data=attestation_data,
        signature=signature,
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
        attestation_1=slashable_attestation_1,
        attestation_2=slashable_attestation_2,
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
            current_justified_epoch=config.GENESIS_EPOCH,
        ),
        config,
        keymap,
        attestation_slot_1,
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        state.copy(
            slot=attestation_slot_1,
            current_justified_epoch=config.GENESIS_EPOCH + 1,  # source_epoch_1 < source_epoch_2
        ),
        config,
        keymap,
        attestation_slot_2,
    )

    return AttesterSlashing(
        attestation_1=slashable_attestation_1,
        attestation_2=slashable_attestation_2,
    )


#
# Attestation
#
def _get_target_root(state: BeaconState,
                     config: Eth2Config,
                     beacon_block_root: Hash32) -> Hash32:

    epoch = slot_to_epoch(state.slot, config.SLOTS_PER_EPOCH)
    epoch_start_slot = get_epoch_start_slot(
        epoch,
        config.SLOTS_PER_EPOCH,
    )
    if epoch_start_slot == state.slot:
        return beacon_block_root
    else:
        return get_block_root(
            state,
            epoch,
            config.SLOTS_PER_EPOCH,
            config.SLOTS_PER_HISTORICAL_ROOT,
        )


def _get_mock_message_and_attesting_indices(
        attestation_data: AttestationData,
        committee: Sequence[ValidatorIndex],
        num_voted_attesters: int) -> Tuple[Hash32, Tuple[ValidatorIndex, ...]]:
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
    attesting_indices = tuple(
        ValidatorIndex(i) for i in random.sample(range(committee_size), num_voted_attesters)
    )

    return message_hash, tuple(sorted(attesting_indices))


def _create_mock_signed_attestation(state: BeaconState,
                                    attestation_data: AttestationData,
                                    attestation_slot: Slot,
                                    committee: Sequence[ValidatorIndex],
                                    num_voted_attesters: int,
                                    keymap: Dict[BLSPubkey, int],
                                    slots_per_epoch: int) -> Attestation:
    """
    Create a mocking attestation of the given ``attestation_data`` slot with ``keymap``.
    """
    message_hash, attesting_indices = _get_mock_message_and_attesting_indices(
        attestation_data,
        committee,
        num_voted_attesters,
    )

    # Use privkeys to sign the attestation
    signatures = [
        sign_transaction(
            message_hash=message_hash,
            privkey=keymap[
                state.validators[
                    committee[committee_index]
                ].pubkey
            ],
            state=state,
            slot=attestation_slot,
            signature_domain=SignatureDomain.DOMAIN_ATTESTATION,
            slots_per_epoch=slots_per_epoch,
        )
        for committee_index in attesting_indices
    ]

    # aggregate signatures and construct participant bitfield
    aggregation_bitfield, aggregate_signature = aggregate_votes(
        bitfield=get_empty_bitfield(len(committee)),
        sigs=(),
        voting_sigs=signatures,
        attesting_indices=attesting_indices,
    )

    # create attestation from attestation_data, particpipant_bitfield, and signature
    return Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=Bitfield(b'\x00' * len(aggregation_bitfield)),
        signature=aggregate_signature,
    )


# TODO(ralexstokes) merge in w/ ``get_committee_assignment``
def get_crosslink_committees_at_slot(
        state: BeaconState,
        slot: Slot,
        config: Eth2Config) -> Tuple[Tuple[Tuple[ValidatorIndex, ...], Shard], ...]:
    epoch = slot_to_epoch(slot, config.SLOTS_PER_EPOCH)
    active_validators = get_active_validator_indices(state.validators, epoch)
    committees_per_slot = get_epoch_committee_count(
        len(active_validators),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    ) // config.SLOTS_PER_EPOCH
    results = []
    offset = committees_per_slot * (slot % config.SLOTS_PER_EPOCH)
    slot_start_shard = Shard((
        get_epoch_start_shard(state, epoch, CommitteeConfig(config)) + offset
    ) % config.SHARD_COUNT)
    for i in range(committees_per_slot):
        shard = (slot_start_shard + i) % config.SHARD_COUNT
        committee = get_crosslink_committee(state, epoch, shard, CommitteeConfig(config))
        results.append((committee, Shard(shard)))

    return tuple(results)


def create_signed_attestation_at_slot(state: BeaconState,
                                      config: Eth2Config,
                                      state_machine: BaseBeaconStateMachine,
                                      attestation_slot: Slot,
                                      beacon_block_root: Hash32,
                                      validator_privkeys: Dict[ValidatorIndex, int],
                                      committee: Tuple[ValidatorIndex, ...],
                                      shard: Shard) -> Attestation:
    """
    Create the attestations of the given ``attestation_slot`` slot with ``validator_privkeys``.
    """
    state_transition = state_machine.state_transition
    state = state_transition.apply_state_transition(
        state,
        future_slot=attestation_slot,
    )

    target_epoch = slot_to_epoch(
        attestation_slot,
        config.SLOTS_PER_EPOCH,
    )

    target_root = _get_target_root(state, config, beacon_block_root)

    parent_crosslink = state.current_crosslinks[shard]

    attestation_data = AttestationData(
        beacon_block_root=beacon_block_root,
        source_epoch=state.current_justified_epoch,
        source_root=state.current_justified_root,
        target_root=target_root,
        target_epoch=target_epoch,
        crosslink=Crosslink(
            shard=shard,
            parent_root=parent_crosslink.root,
            start_epoch=parent_crosslink.end_epoch,
            end_epoch=target_epoch,
        )
    )

    return _create_mock_signed_attestation(
        state,
        attestation_data,
        attestation_slot,
        committee,
        len(committee),
        keymapper(lambda index: state.validators[index].pubkey, validator_privkeys),
        config.SLOTS_PER_EPOCH,
    )


@to_tuple
def create_mock_signed_attestations_at_slot(
        state: BeaconState,
        config: Eth2Config,
        state_machine: BaseBeaconStateMachine,
        attestation_slot: Slot,
        beacon_block_root: Hash32,
        keymap: Dict[BLSPubkey, int],
        voted_attesters_ratio: float=1.0) -> Iterable[Attestation]:
    """
    Create the mocking attestations of the given ``attestation_slot`` slot with ``keymap``.
    """
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state,
        attestation_slot,
        config,
    )

    # Get `target_root`
    target_root = _get_target_root(state, config, beacon_block_root)
    target_epoch = slot_to_epoch(
        state.slot,
        config.SLOTS_PER_EPOCH,
    )

    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee

        parent_crosslink = state.current_crosslinks[shard]

        attestation_data = AttestationData(
            beacon_block_root=beacon_block_root,
            source_epoch=state.current_justified_epoch,
            source_root=state.current_justified_root,
            target_root=target_root,
            target_epoch=target_epoch,
            crosslink=Crosslink(
                shard=shard,
                parent_root=parent_crosslink.root,
                start_epoch=parent_crosslink.end_epoch,
                end_epoch=min(
                    target_epoch,
                    parent_crosslink.end_epoch + config.MAX_EPOCHS_PER_CROSSLINK
                ),
            )
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
def create_mock_voluntary_exit(state: BeaconState,
                               config: Eth2Config,
                               keymap: Dict[BLSPubkey, int],
                               validator_index: ValidatorIndex,
                               exit_epoch: Epoch=None) -> VoluntaryExit:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_epoch = current_epoch if exit_epoch is None else exit_epoch
    voluntary_exit = VoluntaryExit(
        epoch=target_epoch,
        validator_index=validator_index,
    )
    return voluntary_exit.copy(
        signature=sign_transaction(
            message_hash=voluntary_exit.signing_root,
            privkey=keymap[state.validators[validator_index].pubkey],
            state=state,
            slot=get_epoch_start_slot(target_epoch, config.SLOTS_PER_EPOCH),
            signature_domain=SignatureDomain.DOMAIN_VOLUNTARY_EXIT,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
        )
    )


#
# Deposit
#
def create_mock_deposit_data(*,
                             config: Eth2Config,
                             pubkey: BLSPubkey,
                             privkey: int,
                             withdrawal_credentials: Hash32,
                             amount: Gwei=None) -> DepositData:
    if amount is None:
        amount = config.MAX_EFFECTIVE_BALANCE

    data = DepositData(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    signature = sign_proof_of_possession(
        deposit_data=data,
        privkey=privkey,
    )
    return data.copy(
        signature=signature,
    )
