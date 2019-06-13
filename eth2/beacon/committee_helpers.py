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
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon._utils.random import (
    get_shuffled_index,
)
from eth2.beacon import helpers
from eth2.beacon.constants import (
    MAX_RANDOM_BYTE,
)
from eth2.beacon.helpers import (
    generate_seed,
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


# TODO(ralexstokes) this has been deprecated, clean up
# @functools.lru_cache(maxsize=128)
# def get_shuffling(*,
#                   seed: Hash32,
#                   validators: Sequence['Validator'],
#                   epoch: Epoch,
#                   committee_config: CommitteeConfig) -> Tuple[Sequence[ValidatorIndex], ...]:
#     """
#     Shuffle ``validators`` into crosslink committees seeded by ``seed`` and ``epoch``.
#     Return a list of ``committee_per_epoch`` committees where each
#     committee is itself a list of validator indices.

#     If ``get_shuffling(seed, validators, epoch)`` returns some value ``x`` for some
#     ``epoch <= get_current_epoch(state) + ACTIVATION_EXIT_DELAY``, it should return the
#     same value ``x`` for the same ``seed`` and ``epoch`` and possible future modifications
#     of ``validators`` forever in phase 0, and until the ~1 year deletion delay in phase 2
#     and in the future.
#     """
#     slots_per_epoch = committee_config.SLOTS_PER_EPOCH
#     target_committee_size = committee_config.TARGET_COMMITTEE_SIZE
#     shard_count = committee_config.SHARD_COUNT
#     shuffle_round_count = committee_config.SHUFFLE_ROUND_COUNT

#     active_validator_indices = get_active_validator_indices(validators, epoch)

#     committees_per_epoch = get_epoch_committee_count(
#         len(active_validator_indices),
#         shard_count,
#         slots_per_epoch,
#         target_committee_size,
#     )

#     # Shuffle
#     shuffled_active_validator_indices = shuffle(
#         active_validator_indices,
#         seed,
#         shuffle_round_count=shuffle_round_count,
#     )

#     # Split the shuffled list into committees_per_epoch pieces
#     return tuple(
#         split(
#             shuffled_active_validator_indices,
#             committees_per_epoch,
#         )
#     )


# def get_previous_epoch_committee_count(
#         state: 'BeaconState',
#         shard_count: int,
#         slots_per_epoch: int,
#         target_committee_size: int) -> int:
#     previous_active_validators = get_active_validator_indices(
#         state.validator_registry,
#         state.previous_shuffling_epoch,
#     )
#     return get_epoch_committee_count(
#         active_validator_count=len(previous_active_validators),
#         shard_count=shard_count,
#         slots_per_epoch=slots_per_epoch,
#         target_committee_size=target_committee_size,
#     )


# def get_current_epoch_committee_count(
#         state: 'BeaconState',
#         shard_count: int,
#         slots_per_epoch: int,
#         target_committee_size: int) -> int:
#     current_active_validators = get_active_validator_indices(
#         state.validator_registry,
#         state.current_shuffling_epoch,
#     )
#     return get_epoch_committee_count(
#         active_validator_count=len(current_active_validators),
#         shard_count=shard_count,
#         slots_per_epoch=slots_per_epoch,
#         target_committee_size=target_committee_size,
#     )


# def get_next_epoch_committee_count(
#         state: 'BeaconState',
#         shard_count: int,
#         slots_per_epoch: int,
#         target_committee_size: int) -> int:
#     next_active_validators = get_active_validator_indices(
#         state.validator_registry,
#         state.current_shuffling_epoch + 1,
#     )
#     return get_epoch_committee_count(
#         active_validator_count=len(next_active_validators),
#         shard_count=shard_count,
#         slots_per_epoch=slots_per_epoch,
#         target_committee_size=target_committee_size,
#     )


#
# Helpers for get_crosslink_committees_at_slot
#

# def _get_shuffling_context_is_current_epoch(
#         state: 'BeaconState',
#         committee_config: CommitteeConfig) -> ShufflingContext:
#     return ShufflingContext(
#         committees_per_epoch=get_current_epoch_committee_count(
#             state=state,
#             shard_count=committee_config.SHARD_COUNT,
#             slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#             target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#         ),
#         seed=state.current_shuffling_seed,
#         shuffling_epoch=state.current_shuffling_epoch,
#         shuffling_start_shard=state.current_shuffling_start_shard,
#     )


# def _get_shuffling_context_is_previous_epoch(
#         state: 'BeaconState',
#         committee_config: CommitteeConfig) -> ShufflingContext:
#     return ShufflingContext(
#         committees_per_epoch=get_previous_epoch_committee_count(
#             state=state,
#             shard_count=committee_config.SHARD_COUNT,
#             slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#             target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#         ),
#         seed=state.previous_shuffling_seed,
#         shuffling_epoch=state.previous_shuffling_epoch,
#         shuffling_start_shard=state.previous_shuffling_start_shard,
#     )


# def _get_shuffling_contextis_next_epoch_registry_change(
#         state: 'BeaconState',
#         next_epoch: Epoch,
#         committee_config: CommitteeConfig) -> ShufflingContext:
#     current_committees_per_epoch = get_current_epoch_committee_count(
#         state=state,
#         shard_count=committee_config.SHARD_COUNT,
#         slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#         target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#     )
#     return ShufflingContext(
#         committees_per_epoch=get_next_epoch_committee_count(
#             state=state,
#             shard_count=committee_config.SHARD_COUNT,
#             slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#             target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#         ),
#         seed=helpers.generate_seed(
#             state=state,
#             epoch=next_epoch,
#             committee_config=committee_config,
#         ),
#         shuffling_epoch=next_epoch,
#         # for mocking this out in tests.
#         shuffling_start_shard=(
#             state.current_shuffling_start_shard + current_committees_per_epoch
#         ) % committee_config.SHARD_COUNT,
#     )


# def _get_shuffling_contextis_next_epoch_should_reseed(
#         state: 'BeaconState',
#         next_epoch: Epoch,
#         committee_config: CommitteeConfig) -> ShufflingContext:
#     return ShufflingContext(
#         committees_per_epoch=get_next_epoch_committee_count(
#             state=state,
#             shard_count=committee_config.SHARD_COUNT,
#             slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#             target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#         ),
#         # for mocking this out in tests.
#         seed=helpers.generate_seed(
#             state=state,
#             epoch=next_epoch,
#             committee_config=committee_config,
#         ),
#         shuffling_epoch=next_epoch,
#         shuffling_start_shard=state.current_shuffling_start_shard,
#     )


# def _get_shuffling_contextis_next_epoch_no_registry_change_no_reseed(
#         state: 'BeaconState',
#         committee_config: CommitteeConfig) -> ShufflingContext:
#     return ShufflingContext(
#         committees_per_epoch=get_current_epoch_committee_count(
#             state=state,
#             shard_count=committee_config.SHARD_COUNT,
#             slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
#             target_committee_size=committee_config.TARGET_COMMITTEE_SIZE,
#         ),
#         seed=state.current_shuffling_seed,
#         shuffling_epoch=state.current_shuffling_epoch,
#         shuffling_start_shard=state.current_shuffling_start_shard,
#     )


# @to_tuple
# def get_crosslink_committees_at_slot(
#         state: 'BeaconState',
#         slot: Slot,
#         committee_config: CommitteeConfig,
#         registry_change: bool=False) -> Iterable[Tuple[Sequence[ValidatorIndex], Shard]]:
#     """
#     Return the list of ``(committee, shard)`` tuples for the ``slot``.
#     """
#     shard_count = committee_config.SHARD_COUNT
#     slots_per_epoch = committee_config.SLOTS_PER_EPOCH

#     epoch = slot_to_epoch(slot, slots_per_epoch)
#     current_epoch = state.current_epoch(slots_per_epoch)
#     previous_epoch = state.previous_epoch(slots_per_epoch)
#     next_epoch = state.next_epoch(slots_per_epoch)

#     validate_epoch_within_previous_and_next(epoch, previous_epoch, next_epoch)

#     if epoch == current_epoch:
#         shuffling_context = _get_shuffling_context_is_current_epoch(state, committee_config)
#     elif epoch == previous_epoch:
#         shuffling_context = _get_shuffling_context_is_previous_epoch(state, committee_config)
#     elif epoch == next_epoch:
#         epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
#         should_reseed = (
#             epochs_since_last_registry_update > 1 and
#             is_power_of_two(epochs_since_last_registry_update)
#         )

#         if registry_change:
#             shuffling_context = _get_shuffling_contextis_next_epoch_registry_change(
#                 state,
#                 next_epoch,
#                 committee_config,
#             )
#         elif should_reseed:
#             shuffling_context = _get_shuffling_contextis_next_epoch_should_reseed(
#                 state,
#                 next_epoch,
#                 committee_config,
#             )
#         else:
#             shuffling_context = _get_shuffling_contextis_next_epoch_no_registry_change_no_reseed(
#                 state,
#                 committee_config,
#             )

#     shuffling = get_shuffling(
#         seed=shuffling_context.seed,
#         validators=state.validator_registry,
#         epoch=shuffling_context.shuffling_epoch,
#         committee_config=committee_config,
#     )
#     offset = slot % slots_per_epoch
#     committees_per_slot = shuffling_context.committees_per_epoch // slots_per_epoch
#     slot_start_shard = (
#         shuffling_context.shuffling_start_shard +
#         committees_per_slot * offset
#     ) % shard_count

#     for index in range(committees_per_slot):
#         committee = shuffling[committees_per_slot * offset + index]
#         yield (
#             committee,
#             Shard((slot_start_shard + index) % shard_count),
#         )


def get_beacon_proposer_index(state: 'BeaconState',
                              committee_config: CommitteeConfig) -> ValidatorIndex:
    """
    Return the current beacon proposer index.
    """
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH
    shard_count = committee_config.SHARD_COUNT
    target_committee_size = committee_config.TARGET_COMMITTEE_SIZE
    max_effective_balance = committee_config.MAX_EFFECTIVE_BALANCE

    current_slot = state.slot
    current_epoch = state.current_epoch(slots_per_epoch)
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    committees_per_slot = get_epoch_committee_count(
        len(active_validator_indices),
        shard_count,
        slots_per_epoch,
        target_committee_size,
    ) // slots_per_epoch
    offset = committees_per_slot * (current_slot % slots_per_epoch)
    shard = (
        get_epoch_start_shard(state, current_epoch, committee_config) + offset
    ) % shard_count
    first_committee = get_crosslink_committee(
        state,
        current_epoch,
        shard,
        committee_config,
    )
    seed = generate_seed(state, current_epoch, committee_config)
    i = 0
    first_committee_len = len(first_committee)
    while True:
        candidate_index = first_committee[(current_epoch + i) % first_committee_len]
        random_byte = hash(seed + (i // 32).to_bytes(8, "little"))[i % 32]
        effective_balance = state.validator_registry[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= max_effective_balance * random_byte:
            return candidate_index
        i += 1


def _get_shard_delta(state: 'BeaconState',
                     epoch: Epoch,
                     config: CommitteeConfig) -> int:
    shard_count = config.SHARD_COUNT
    slots_per_epoch = config.SLOTS_PER_EPOCH

    active_validator_indices = get_active_validator_indices(state, epoch)

    return min(
        get_epoch_committee_count(
            len(active_validator_indices),
            shard_count,
            slots_per_epoch,
            config.TARGET_COMMITTEE_SIZE,
        ),
        shard_count - shard_count // slots_per_epoch
    )


def get_epoch_start_shard(state: 'BeaconState',
                          epoch: Epoch,
                          config: CommitteeConfig) -> Shard:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    if epoch > next_epoch:
        raise ValidationError("Asking for start shard for an epoch after next")

    check_epoch = next_epoch
    shard = (
        state.latest_start_shard + _get_shard_delta(state, current_epoch)
    ) % config.SHARD_COUNT
    while check_epoch > epoch:
        check_epoch -= 1
        shard = (
            shard + config.SHARD_COUNT - _get_shard_delta(state, check_epoch)
        ) % config.SHARD_COUNT
    return shard


def _compute_committee(indices: Sequence[ValidatorIndex],
                       seed: Hash32,
                       index: int,
                       count: int) -> Iterable[ValidatorIndex]:
    start = (len(index) * index) // count
    end = (len(index) * (index + 1)) // count
    for i in range(start, end):
        shuffled_index = get_shuffled_index(i, len(indices), seed)
        yield indices[shuffled_index]


@to_tuple
def get_crosslink_committee(state: 'BeaconState',
                            epoch: Epoch,
                            shard: Shard,
                            config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    target_shard = (
        shard + config.SHARD_COUNT - get_epoch_start_shard(state, epoch)
    ) % config.SHARD_COUNT

    return _compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=generate_seed(state, epoch),
        index=target_shard,
        count=get_epoch_committee_count(state, epoch),
    )


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
