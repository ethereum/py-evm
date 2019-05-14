import functools
from typing import (
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

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
from eth2._utils.numeric import (
    is_power_of_two,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon._utils.random import (
    shuffle,
    split,
)
from eth2.beacon import helpers
from eth2.beacon.helpers import (
    get_active_validator_indices,
    slot_to_epoch,
)
from eth2.beacon.datastructures.shuffling_context import (
    ShufflingContext,
)
from eth2.beacon.typing import (
    Bitfield,
    Epoch,
    Shard,
    Slot,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
    validate_epoch_within_previous_and_next,
)

if TYPE_CHECKING:
    from eth2.beacon.types.attestations import Attestation  # noqa: F401
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.validators import Validator  # noqa: F401


def get_epoch_committee_count(
        active_validator_count: int,
        shard_count: int,
        slots_per_epoch: int,
        target_committee_size: int) -> int:
    return max(
        1,
        min(
            shard_count // slots_per_epoch,
            active_validator_count // slots_per_epoch // target_committee_size,
        )
    ) * slots_per_epoch


@functools.lru_cache(maxsize=128)
def get_shuffling(*,
                  seed: Hash32,
                  validators: Sequence['Validator'],
                  epoch: Epoch,
                  committee_config: CommitteeConfig) -> Tuple[Sequence[ValidatorIndex], ...]:
    """
    Shuffle ``validators`` into crosslink committees seeded by ``seed`` and ``epoch``.
    Return a list of ``committee_per_epoch`` committees where each
    committee is itself a list of validator indices.

    If ``get_shuffling(seed, validators, epoch)`` returns some value ``x`` for some
    ``epoch <= get_current_epoch(state) + ACTIVATION_EXIT_DELAY``, it should return the
    same value ``x`` for the same ``seed`` and ``epoch`` and possible future modifications
    of ``validators`` forever in phase 0, and until the ~1 year deletion delay in phase 2
    and in the future.
    """
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH
    target_committee_size = committee_config.TARGET_COMMITTEE_SIZE
    shard_count = committee_config.SHARD_COUNT
    shuffle_round_count = committee_config.SHUFFLE_ROUND_COUNT

    active_validator_indices = get_active_validator_indices(validators, epoch)

    committees_per_epoch = get_epoch_committee_count(
        len(active_validator_indices),
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )

    # Shuffle
    shuffled_active_validator_indices = shuffle(
        active_validator_indices,
        seed,
        shuffle_round_count=shuffle_round_count,
    )

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
        slots_per_epoch: int,
        target_committee_size: int) -> int:
    previous_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.previous_shuffling_epoch,
    )
    return get_epoch_committee_count(
        active_validator_count=len(previous_active_validators),
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


def get_current_epoch_committee_count(
        state: 'BeaconState',
        shard_count: int,
        slots_per_epoch: int,
        target_committee_size: int) -> int:
    current_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_shuffling_epoch,
    )
    return get_epoch_committee_count(
        active_validator_count=len(current_active_validators),
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


def get_next_epoch_committee_count(
        state: 'BeaconState',
        shard_count: int,
        slots_per_epoch: int,
        target_committee_size: int) -> int:
    next_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_shuffling_epoch + 1,
    )
    return get_epoch_committee_count(
        active_validator_count=len(next_active_validators),
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


#
# Helpers for get_crosslink_committees_at_slot
#

def _get_shuffling_context_is_current_epoch(
        state: 'BeaconState',
        committee_config: CommitteeConfig) -> ShufflingContext:
    return ShufflingContext(
        committees_per_epoch=get_current_epoch_committee_count(
            state=state,
            shard_count=committee_config.SHARD_COUNT,
            slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
            target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
        ),
        seed=state.current_shuffling_seed,
        shuffling_epoch=state.current_shuffling_epoch,
        shuffling_start_shard=state.current_shuffling_start_shard,
    )


def _get_shuffling_context_is_previous_epoch(
        state: 'BeaconState',
        committee_config: CommitteeConfig) -> ShufflingContext:
    return ShufflingContext(
        committees_per_epoch=get_previous_epoch_committee_count(
            state=state,
            shard_count=committee_config.SHARD_COUNT,
            slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
            target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
        ),
        seed=state.previous_shuffling_seed,
        shuffling_epoch=state.previous_shuffling_epoch,
        shuffling_start_shard=state.previous_shuffling_start_shard,
    )


def _get_shuffling_contextis_next_epoch_registry_change(
        state: 'BeaconState',
        next_epoch: Epoch,
        committee_config: CommitteeConfig) -> ShufflingContext:
    current_committees_per_epoch = get_current_epoch_committee_count(
        state=state,
        shard_count=committee_config.SHARD_COUNT,
        slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
        target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
    )
    return ShufflingContext(
        committees_per_epoch=get_next_epoch_committee_count(
            state=state,
            shard_count=committee_config.SHARD_COUNT,
            slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
            target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
        ),
        seed=helpers.generate_seed(
            state=state,
            epoch=next_epoch,
            committee_config=committee_config,
        ),
        shuffling_epoch=next_epoch,
        # for mocking this out in tests.
        shuffling_start_shard=(
            state.current_shuffling_start_shard + current_committees_per_epoch
        ) % committee_config.SHARD_COUNT,
    )


def _get_shuffling_contextis_next_epoch_should_reseed(
        state: 'BeaconState',
        next_epoch: Epoch,
        committee_config: CommitteeConfig) -> ShufflingContext:
    return ShufflingContext(
        committees_per_epoch=get_next_epoch_committee_count(
            state=state,
            shard_count=committee_config.SHARD_COUNT,
            slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
            target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
        ),
        # for mocking this out in tests.
        seed=helpers.generate_seed(
            state=state,
            epoch=next_epoch,
            committee_config=committee_config,
        ),
        shuffling_epoch=next_epoch,
        shuffling_start_shard=state.current_shuffling_start_shard,
    )


def _get_shuffling_contextis_next_epoch_no_registry_change_no_reseed(
        state: 'BeaconState',
        committee_config: CommitteeConfig) -> ShufflingContext:
    return ShufflingContext(
        committees_per_epoch=get_current_epoch_committee_count(
            state=state,
            shard_count=committee_config.SHARD_COUNT,
            slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
            target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
        ),
        seed=state.current_shuffling_seed,
        shuffling_epoch=state.current_shuffling_epoch,
        shuffling_start_shard=state.current_shuffling_start_shard,
    )


@to_tuple
def get_crosslink_committees_at_slot(
        state: 'BeaconState',
        slot: Slot,
        committee_config: CommitteeConfig,
        registry_change: bool=False) -> Iterable[Tuple[Sequence[ValidatorIndex], Shard]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.
    """
    shard_count = committee_config.SHARD_COUNT
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH

    epoch = slot_to_epoch(slot, slots_per_epoch)
    current_epoch = state.current_epoch(slots_per_epoch)
    previous_epoch = state.previous_epoch(slots_per_epoch)
    next_epoch = state.next_epoch(slots_per_epoch)

    validate_epoch_within_previous_and_next(epoch, previous_epoch, next_epoch)

    if epoch == current_epoch:
        shuffling_context = _get_shuffling_context_is_current_epoch(state, committee_config)
    elif epoch == previous_epoch:
        shuffling_context = _get_shuffling_context_is_previous_epoch(state, committee_config)
    elif epoch == next_epoch:
        epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
        should_reseed = (
            epochs_since_last_registry_update > 1 and
            is_power_of_two(epochs_since_last_registry_update)
        )

        if registry_change:
            shuffling_context = _get_shuffling_contextis_next_epoch_registry_change(
                state,
                next_epoch,
                committee_config,
            )
        elif should_reseed:
            shuffling_context = _get_shuffling_contextis_next_epoch_should_reseed(
                state,
                next_epoch,
                committee_config,
            )
        else:
            shuffling_context = _get_shuffling_contextis_next_epoch_no_registry_change_no_reseed(
                state,
                committee_config,
            )

    shuffling = get_shuffling(
        seed=shuffling_context.seed,
        validators=state.validator_registry,
        epoch=shuffling_context.shuffling_epoch,
        committee_config=committee_config,
    )
    offset = slot % slots_per_epoch
    committees_per_slot = shuffling_context.committees_per_epoch // slots_per_epoch
    slot_start_shard = (
        shuffling_context.shuffling_start_shard +
        committees_per_slot * offset
    ) % shard_count

    for index in range(committees_per_slot):
        committee = shuffling[committees_per_slot * offset + index]
        yield (
            committee,
            Shard((slot_start_shard + index) % shard_count),
        )


def get_beacon_proposer_index(state: 'BeaconState',
                              slot: Slot,
                              committee_config: CommitteeConfig,
                              registry_change: bool=False) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    epoch = slot_to_epoch(slot, committee_config.SLOTS_PER_EPOCH)
    previous_epoch = state.previous_epoch(committee_config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(committee_config.SLOTS_PER_EPOCH)

    validate_epoch_within_previous_and_next(epoch, previous_epoch, next_epoch)

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        committee_config=committee_config,
        registry_change=registry_change,
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

    return first_committee[epoch % len(first_committee)]


@to_tuple
def get_crosslink_committee_for_attestation(
        state: 'BeaconState',
        attestation_data: 'AttestationData',
        committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    """
    Return the specific crosslink committee concerning the given ``attestation_data``.
    In particular, the (slot, shard) coordinate in the ``attestation_data`` selects one committee
    from all committees expected to attest at the slot.

    Raise `ValidationError` in the case that this attestation references a shard that
    is not covered in the specified slot.
    """
    crosslink_committees = get_crosslink_committees_at_slot(
        state=state,
        slot=attestation_data.slot,
        committee_config=committee_config,
    )

    try:
        return next(
            committee for (
                committee,
                shard,
            ) in crosslink_committees if shard == attestation_data.shard
        )
    except StopIteration:
        raise ValidationError(
            "attestation_data.shard ({}) is not in crosslink_committees".format(
                attestation_data.shard,
            )
        )


@to_tuple
def get_members_from_bitfield(committee: Sequence[ValidatorIndex],
                              bitfield: Bitfield) -> Iterable[ValidatorIndex]:
    """
    Return all indices in ``committee`` if they "voted" according to the
    ``bitfield``.

    Raise ``ValidationError`` if the ``bitfield`` does not conform to some
    basic checks around length and zero-padding based on the ``committee``
    length.
    """
    validate_bitfield(bitfield, len(committee))

    # Extract committee members if the corresponding bit is set in the bitfield
    for bitfield_index, validator_index in enumerate(committee):
        if has_voted(bitfield, bitfield_index):
            yield validator_index


def get_attestation_participants(state: 'BeaconState',
                                 attestation_data: 'AttestationData',
                                 bitfield: Bitfield,
                                 committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    """
    Return the participant indices at for the ``attestation_data`` and ``bitfield``.
    """
    committee = get_crosslink_committee_for_attestation(
        state,
        attestation_data,
        committee_config,
    )

    return get_members_from_bitfield(committee, bitfield)


@to_tuple
@to_set
def get_attester_indices_from_attestations(
        *,
        state: 'BeaconState',
        attestations: Sequence['Attestation'],
        committee_config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    for a in attestations:
        yield from get_attestation_participants(
            state,
            a.data,
            a.aggregation_bitfield,
            committee_config,
        )
