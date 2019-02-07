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
from eth2._utils import bls
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
)
from eth2.beacon.helpers import (
    get_block_root,
    get_domain,
    get_epoch_start_slot,
    slot_to_epoch,
)
from eth2.beacon.state_machines.configs import BeaconConfig
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    BLSPubkey,
    BLSSignature,
    Bitfield,
    CommitteeIndex,
    SlotNumber,
    ValidatorIndex,
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
                             slot: SlotNumber,
                             epoch_length: int) -> BLSSignature:
    domain = get_domain(
        fork,
        slot_to_epoch(slot, epoch_length),
        SignatureDomain.DOMAIN_DEPOSIT,
    )
    return bls.sign(
        message=deposit_input.root,
        privkey=privkey,
        domain=domain,
    )


def sign_attestation(message: bytes,
                     privkey: int,
                     fork: Fork,
                     slot: SlotNumber,
                     epoch_length: int) -> BLSSignature:
    domain = get_domain(
        fork,
        slot_to_epoch(slot, epoch_length),
        SignatureDomain.DOMAIN_ATTESTATION,
    )
    return bls.sign(
        message=message,
        privkey=privkey,
        domain=domain,
    )


#
# Only for test/simulation
#
def _get_mock_message_and_voting_committee_indices(
        attestation_data: AttestationData,
        committee: Sequence[ValidatorIndex],
        num_voted_attesters: int) -> Tuple[bytes, Tuple[CommitteeIndex]]:
    """
    Get ``message`` and voting indices of the given ``committee``.
    """
    message = AttestationDataAndCustodyBit.create_attestation_message(attestation_data)

    committee_size = len(committee)
    assert num_voted_attesters <= committee_size

    # Index in committee
    voting_committee_indices = tuple(random.sample(range(committee_size), num_voted_attesters))

    return message, voting_committee_indices


def create_mock_signed_attestation(state: BeaconState,
                                   attestation_data: AttestationData,
                                   committee: Sequence[ValidatorIndex],
                                   num_voted_attesters: int,
                                   keymap: Dict[BLSPubkey, int],
                                   epoch_length: int) -> Attestation:
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
        sign_attestation(
            message=message,
            privkey=keymap[
                state.validator_registry[
                    committee[committee_index]
                ].pubkey
            ],
            fork=state.fork,
            slot=attestation_data.slot,
            epoch_length=epoch_length,
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
        custody_bitfield=b'',
        aggregate_signature=aggregate_signature,
    )


@to_tuple
def create_mock_signed_attestations_at_slot(
        state: BeaconState,
        config: BeaconConfig,
        attestation_slot: SlotNumber,
        keymap: Dict[BLSPubkey, int],
        voted_attesters_ratio: float=1.0) -> Iterable[Attestation]:
    """
    Create the mocking attestations of the given ``attestation_slot`` slot with ``keymap``.
    """
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state.copy(
            slot=state.slot + 1,
        ),
        slot=attestation_slot,
        genesis_epoch=config.GENESIS_EPOCH,
        epoch_length=config.EPOCH_LENGTH,
        target_committee_size=config.TARGET_COMMITTEE_SIZE,
        shard_count=config.SHARD_COUNT,
    )
    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee

        num_voted_attesters = int(len(committee) * voted_attesters_ratio)
        latest_crosslink_root = state.latest_crosslinks[shard].shard_block_root

        attestation_data = AttestationData(
            slot=attestation_slot,
            shard=shard,
            beacon_block_root=ZERO_HASH32,
            epoch_boundary_root=ZERO_HASH32,
            shard_block_root=ZERO_HASH32,
            latest_crosslink_root=latest_crosslink_root,
            justified_epoch=state.previous_justified_epoch,
            justified_block_root=get_block_root(
                state,
                get_epoch_start_slot(state.previous_justified_epoch, config.EPOCH_LENGTH),
                config.LATEST_BLOCK_ROOTS_LENGTH,
            ),
        )

        yield create_mock_signed_attestation(
            state,
            attestation_data,
            committee,
            num_voted_attesters,
            keymap,
            config.EPOCH_LENGTH,
        )
