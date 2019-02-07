from typing import (
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_utils import (
    to_tuple,
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth2._utils.bitfield import (
    has_voted,
)
from eth2._utils.numeric import (
    bitwise_xor,
)
from eth2.beacon._utils.random import (
    shuffle,
    split,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    slot_to_epoch,
)

from eth2.beacon.typing import (
    Bitfield,
    EpochNumber,
    ShardNumber,
    SlotNumber,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
    validate_epoch_for_current_epoch,
)

if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


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
