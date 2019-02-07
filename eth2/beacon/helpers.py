from typing import (
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

import functools

from eth_utils import (
    to_tuple,
    to_set,
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth2._utils.bitfield import (
    has_voted,
)
import eth2._utils.bls as bls
from eth2._utils.numeric import (
    bitwise_xor,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon._utils.random import (
    shuffle,
    split,
)
from eth2.beacon.exceptions import NoWinningRootError
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.types.pending_attestation_records import (
    PendingAttestationRecord,
)
from eth2.beacon.typing import (
    Bitfield,
    BLSPubkey,
    EpochNumber,
    Gwei,
    ShardNumber,
    SlotNumber,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
    validate_epoch_for_active_index_root,
    validate_epoch_for_active_randao_mix,
    validate_epoch_for_current_epoch,
)

if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.fork import Fork  # noqa: F401
    from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


#
# Get block root
#
def _get_block_root(
        latest_block_roots: Sequence[Hash32],
        state_slot: SlotNumber,
        slot: SlotNumber,
        latest_block_roots_length: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    if state_slot > slot + latest_block_roots_length:
        raise ValidationError(
            "state.slot ({}) should be less than or equal to "
            "(slot + latest_block_roots_length) ({}), "
            "where slot={}, latest_block_roots_length={}".format(
                state_slot,
                slot + latest_block_roots_length,
                slot,
                latest_block_roots_length,
            )
        )
    if slot >= state_slot:
        raise ValidationError(
            "slot ({}) should be less than state.slot ({})".format(
                slot,
                state_slot,
            )
        )
    return latest_block_roots[slot % latest_block_roots_length]


def get_block_root(
        state: 'BeaconState',
        slot: SlotNumber,
        latest_block_roots_length: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    return _get_block_root(
        state.latest_block_roots,
        state.slot,
        slot,
        latest_block_roots_length,
    )


def get_randao_mix(state: 'BeaconState',
                   epoch: EpochNumber,
                   epoch_length: int,
                   latest_randao_mixes_length: int) -> Hash32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    validate_epoch_for_active_randao_mix(
        state.current_epoch(epoch_length),
        epoch,
        latest_randao_mixes_length,
    )

    return state.latest_randao_mixes[epoch % latest_randao_mixes_length]


def get_active_validator_indices(validators: Sequence['ValidatorRecord'],
                                 epoch: EpochNumber) -> Tuple[ValidatorIndex, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        ValidatorIndex(index)
        for index, validator in enumerate(validators)
        if validator.is_active(epoch)
    )


#
# Shuffling
#
def get_epoch_committee_count(
        active_validator_count: int,
        shard_count: int,
        epoch_length: int,
        target_committee_size: int) -> int:
    return max(
        1,
        min(
            shard_count // epoch_length,
            active_validator_count // epoch_length // target_committee_size,
        )
    ) * epoch_length


def get_shuffling(*,
                  seed: Hash32,
                  validators: Sequence['ValidatorRecord'],
                  epoch: EpochNumber,
                  epoch_length: int,
                  target_committee_size: int,
                  shard_count: int) -> Tuple[Iterable[ValidatorIndex], ...]:
    """
    Shuffle ``validators`` into crosslink committees seeded by ``seed`` and ``epoch``.
    Return a list of ``committee_per_epoch`` committees where each
    committee is itself a list of validator indices.

    If ``get_shuffling(seed, validators, epoch)`` returns some value ``x`` for some
    ``epoch <= get_current_epoch(state) + ENTRY_EXIT_DELAY``, it should return the
    same value ``x`` for the same ``seed`` and ``epoch`` and possible future modifications
    of ``validators`` forever in phase 0, and until the ~1 year deletion delay in phase 2
    and in the future.
    """
    active_validator_indices = get_active_validator_indices(validators, epoch)

    committees_per_epoch = get_epoch_committee_count(
        len(active_validator_indices),
        shard_count,
        epoch_length,
        target_committee_size,
    )

    # Shuffle
    seed = bitwise_xor(seed, Hash32(epoch.to_bytes(32, byteorder="big")))
    shuffled_active_validator_indices = shuffle(active_validator_indices, seed)

    # Split the shuffled list into committees_per_epoch pieces
    return tuple(
        split(
            shuffled_active_validator_indices,
            committees_per_epoch,
        )
    )


def get_previous_epoch_committee_count(
        state: 'BeaconState',
        shard_count: int,
        epoch_length: int,
        target_committee_size: int) -> int:
    previous_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.previous_calculation_epoch,
    )
    return get_epoch_committee_count(
        active_validator_count=len(previous_active_validators),
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


def get_current_epoch_committee_count(
        state: 'BeaconState',
        shard_count: int,
        epoch_length: int,
        target_committee_size: int) -> int:
    current_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_calculation_epoch,
    )
    return get_epoch_committee_count(
        active_validator_count=len(current_active_validators),
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


@to_tuple
def get_crosslink_committees_at_slot(
        state: 'BeaconState',
        slot: SlotNumber,
        genesis_epoch: EpochNumber,
        epoch_length: int,
        target_committee_size: int,
        shard_count: int) -> Iterable[Tuple[Iterable[ValidatorIndex], ShardNumber]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.
    """

    epoch = slot_to_epoch(slot, epoch_length)
    current_epoch = state.current_epoch(epoch_length)

    validate_epoch_for_current_epoch(
        current_epoch=current_epoch,
        given_epoch=epoch,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
    )

    # TODO: need to update according to https://github.com/ethereum/eth2.0-specs/pull/520
    if epoch < current_epoch:
        committees_per_epoch = get_previous_epoch_committee_count(
            state=state,
            shard_count=shard_count,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
        )
        seed = state.previous_epoch_seed
        shuffling_epoch = state.previous_calculation_epoch
        shuffling_start_shard = state.previous_epoch_start_shard
    else:
        committees_per_epoch = get_current_epoch_committee_count(
            state=state,
            shard_count=shard_count,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
        )
        seed = state.current_epoch_seed
        shuffling_epoch = state.current_calculation_epoch
        shuffling_start_shard = state.current_epoch_start_shard

    shuffling = get_shuffling(
        seed=seed,
        validators=state.validator_registry,
        epoch=shuffling_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    offset = slot % epoch_length
    committees_per_slot = committees_per_epoch // epoch_length
    slot_start_shard = (
        shuffling_start_shard +
        committees_per_slot * offset
    ) % shard_count

    for index in range(committees_per_slot):
        committee = shuffling[committees_per_slot * offset + index]
        yield (
            committee,
            ShardNumber((slot_start_shard + index) % shard_count),
        )


def get_active_index_root(state: 'BeaconState',
                          epoch: EpochNumber,
                          epoch_length: int,
                          entry_exit_delay: int,
                          latest_index_roots_length: int) -> Hash32:
    """
    Return the index root at a recent ``epoch``.
    """
    validate_epoch_for_active_index_root(
        state.current_epoch(epoch_length),
        epoch,
        entry_exit_delay,
        latest_index_roots_length,
    )

    return state.latest_index_roots[epoch % latest_index_roots_length]


def generate_seed(state: 'BeaconState',
                  epoch: EpochNumber,
                  epoch_length: int,
                  seed_lookahead: int,
                  entry_exit_delay: int,
                  latest_index_roots_length: int,
                  latest_randao_mixes_length: int) -> Hash32:
    """
    Generate a seed for the given ``epoch``.
    """
    randao_mix = get_randao_mix(
        state=state,
        epoch=EpochNumber(epoch - seed_lookahead),
        epoch_length=epoch_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    active_index_root = get_active_index_root(
        state=state,
        epoch=epoch,
        epoch_length=epoch_length,
        entry_exit_delay=entry_exit_delay,
        latest_index_roots_length=latest_index_roots_length,
    )

    return hash_eth2(randao_mix + active_index_root)


def get_beacon_proposer_index(state: 'BeaconState',
                              slot: SlotNumber,
                              genesis_epoch: EpochNumber,
                              epoch_length: int,
                              target_committee_size: int,
                              shard_count: int) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    try:
        first_crosslink_committee = crosslink_committees_at_slot[0]
    except IndexError:
        raise ValidationError("crosslink_committees should not be empty.")

    first_committee, _ = first_crosslink_committee
    if len(first_committee) <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    return first_committee[slot % len(first_committee)]


def _get_committee_for_shard(
        crosslink_committees: Sequence[Tuple[Sequence[ValidatorIndex], ShardNumber]],
        shard: ShardNumber) -> Iterable[ValidatorIndex]:
    for committee, committee_shard in crosslink_committees:
        if committee_shard == shard:
            return committee
    return None


@to_tuple
def get_attestation_participants(state: 'BeaconState',
                                 attestation_data: 'AttestationData',
                                 bitfield: Bitfield,
                                 genesis_epoch: EpochNumber,
                                 epoch_length: int,
                                 target_committee_size: int,
                                 shard_count: int) -> Iterable[ValidatorIndex]:
    """
    Return the participant indices at for the ``attestation_data`` and ``bitfield``.
    """
    # Find the committee in the list with the desired shard
    crosslink_committees = get_crosslink_committees_at_slot(
        state=state,
        slot=attestation_data.slot,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    if attestation_data.shard not in set([shard for _, shard in crosslink_committees]):
        raise ValidationError(
            "attestation_data.shard ({}) is not in crosslink_committees".format(
                attestation_data.shard,
            )
        )

    try:
        # Filter by shard
        committee = tuple(
            _get_committee_for_shard(crosslink_committees, attestation_data.shard)
        )
    except IndexError:
        raise ValidationError(
            "committee for shard={} should not be empty.".format(
                attestation_data.shard,
            )
        )

    validate_bitfield(bitfield, len(committee))

    # Find the participating attesters in the committee
    for bitfield_index, validator_index in enumerate(committee):
        if has_voted(bitfield, bitfield_index):
            yield validator_index


#
# Per-epoch processing helpers
#
@to_tuple
def get_current_epoch_attestations(
        state: 'BeaconState',
        epoch_length: int) -> Iterable[PendingAttestationRecord]:
    for attestation in state.latest_attestations:
        if state.current_epoch(epoch_length) == slot_to_epoch(attestation.data.slot, epoch_length):
            yield attestation


@to_tuple
def get_previous_epoch_attestations(
        state: 'BeaconState',
        epoch_length: int,
        genesis_epoch: EpochNumber) -> Iterable[PendingAttestationRecord]:
    previous_epoch = state.previous_epoch(epoch_length, genesis_epoch)
    for attestation in state.latest_attestations:
        if previous_epoch == slot_to_epoch(attestation.data.slot, epoch_length):
            yield attestation


@to_tuple
@to_set
def get_attesting_validator_indices(
        *,
        state: 'BeaconState',
        attestations: Sequence[PendingAttestationRecord],
        shard: ShardNumber,
        shard_block_root: Hash32,
        genesis_epoch: EpochNumber,
        epoch_length: int,
        target_committee_size: int,
        shard_count: int) -> Iterable[ValidatorIndex]:
    """
    Loop through ``attestations`` and check if ``shard``/``shard_block_root`` in the attestation
    matches the given ``shard``/``shard_block_root``.
    If the attestation matches, get the index of the participating validators.
    Finally, return the union of the indices.
    """
    for a in attestations:
        if a.data.shard == shard and a.data.shard_block_root == shard_block_root:
            yield from get_attestation_participants(
                state,
                a.data,
                a.aggregation_bitfield,
                genesis_epoch,
                epoch_length,
                target_committee_size,
                shard_count,
            )


def get_total_attesting_balance(
        *,
        state: 'BeaconState',
        shard: ShardNumber,
        shard_block_root: Hash32,
        attestations: Sequence[PendingAttestationRecord],
        genesis_epoch: EpochNumber,
        epoch_length: int,
        max_deposit_amount: Gwei,
        target_committee_size: int,
        shard_count: int) -> Gwei:
    return Gwei(
        sum(
            get_effective_balance(state.validator_balances, i, max_deposit_amount)
            for i in get_attesting_validator_indices(
                state=state,
                attestations=attestations,
                shard=shard,
                shard_block_root=shard_block_root,
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length,
                target_committee_size=target_committee_size,
                shard_count=shard_count,
            )
        )
    )


def get_winning_root(
        *,
        state: 'BeaconState',
        shard: ShardNumber,
        attestations: Sequence[PendingAttestationRecord],
        genesis_epoch: EpochNumber,
        epoch_length: int,
        max_deposit_amount: Gwei,
        target_committee_size: int,
        shard_count: int) -> Tuple[Hash32, Gwei]:
    winning_root = None
    winning_root_balance: Gwei = Gwei(0)
    shard_block_roots = set(
        [
            a.data.shard_block_root for a in attestations
            if a.data.shard == shard
        ]
    )
    for shard_block_root in shard_block_roots:
        total_attesting_balance = get_total_attesting_balance(
            state=state,
            shard=shard,
            shard_block_root=shard_block_root,
            attestations=attestations,
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length,
            max_deposit_amount=max_deposit_amount,
            target_committee_size=target_committee_size,
            shard_count=shard_count,
        )
        if total_attesting_balance > winning_root_balance:
            winning_root = shard_block_root
            winning_root_balance = total_attesting_balance
        elif total_attesting_balance == winning_root_balance and winning_root_balance > 0:
            if shard_block_root < winning_root:
                winning_root = shard_block_root

    if winning_root is None:
        raise NoWinningRootError
    return (winning_root, winning_root_balance)


#
# Misc
#
def slot_to_epoch(slot: SlotNumber, epoch_length: int) -> EpochNumber:
    return EpochNumber(slot // epoch_length)


def get_epoch_start_slot(epoch: EpochNumber, epoch_length: int) -> SlotNumber:
    return SlotNumber(epoch * epoch_length)


def get_effective_balance(
        validator_balances: Sequence[Gwei],
        index: ValidatorIndex,
        max_deposit_amount: Gwei) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a
    ``validator`` with the given ``index``.
    """
    return min(validator_balances[index], max_deposit_amount)


def get_fork_version(fork: 'Fork',
                     epoch: EpochNumber) -> int:
    """
    Return the current ``fork_version`` from the given ``fork`` and ``epoch``.
    """
    if epoch < fork.epoch:
        return fork.previous_version
    else:
        return fork.current_version


def get_domain(fork: 'Fork',
               epoch: EpochNumber,
               domain_type: SignatureDomain) -> int:
    """
    Return the domain number of the current fork and ``domain_type``.
    """
    # 2 ** 32 = 4294967296
    return get_fork_version(
        fork,
        epoch,
    ) * 4294967296 + domain_type


@to_tuple
def get_pubkey_for_indices(validators: Sequence['ValidatorRecord'],
                           indices: Sequence[ValidatorIndex]) -> Iterable[BLSPubkey]:
    for index in indices:
        yield validators[index].pubkey


@to_tuple
def generate_aggregate_pubkeys(
        validators: Sequence['ValidatorRecord'],
        slashable_attestation: 'SlashableAttestation') -> Iterable[BLSPubkey]:
    """
    Compute the aggregate pubkey we expect based on
    the proof-of-custody indices found in the ``slashable_attestation``.
    """
    all_indices = slashable_attestation.custody_bit_indices
    get_pubkeys = functools.partial(get_pubkey_for_indices, validators)
    return map(
        bls.aggregate_pubkeys,
        map(get_pubkeys, all_indices),
    )


def verify_slashable_attestation_signature(state: 'BeaconState',
                                           slashable_attestation: 'SlashableAttestation',
                                           epoch_length: int) -> bool:
    """
    Ensure we have a valid aggregate signature for the ``slashable_attestation``.
    """
    pubkeys = generate_aggregate_pubkeys(state.validator_registry, slashable_attestation)

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
    # [TO BE REMOVED IN PHASE 1]
    if not slashable_attestation.is_custody_bitfield_empty:
        raise ValidationError(
            "`slashable_attestation.custody_bitfield` is not empty."
        )

    if len(slashable_attestation.validator_indices) == 0:
        raise ValidationError(
            "`slashable_attestation.validator_indices` is empty."
        )

    if not slashable_attestation.is_validator_indices_ascending:
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


def is_double_vote(attestation_data_1: 'AttestationData',
                   attestation_data_2: 'AttestationData',
                   epoch_length: int) -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'double vote'.
    """
    return (
        slot_to_epoch(attestation_data_1.slot, epoch_length) ==
        slot_to_epoch(attestation_data_2.slot, epoch_length)
    )


def is_surround_vote(attestation_data_1: 'AttestationData',
                     attestation_data_2: 'AttestationData',
                     epoch_length: int) -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'surround vote'.

    Note: parameter order matters as this function only checks
    that ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    source_epoch_1 = attestation_data_1.justified_epoch
    source_epoch_2 = attestation_data_2.justified_epoch
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot, epoch_length)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot, epoch_length)
    return (
        (source_epoch_1 < source_epoch_2) and
        (source_epoch_2 + 1 == target_epoch_2) and
        (target_epoch_2 < target_epoch_1)
    )


def get_entry_exit_effect_epoch(
        epoch: EpochNumber,
        entry_exit_delay: int) -> EpochNumber:
    """
    An entry or exit triggered in the ``epoch`` given by the input takes effect at
    the epoch given by the output.
    """
    return EpochNumber(epoch + 1 + entry_exit_delay)
