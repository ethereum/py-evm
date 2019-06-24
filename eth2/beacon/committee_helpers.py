from typing import (
    Iterable,
    Sequence,
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
from eth2.beacon.constants import (
    MAX_RANDOM_BYTE,
)
from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
)
from eth2.beacon.typing import (
    Bitfield,
    Epoch,
    Shard,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_bitfield,
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


def get_shard_delta(state: 'BeaconState',
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
        state.latest_start_shard + get_shard_delta(state, current_epoch)
    ) % config.SHARD_COUNT
    while check_epoch > epoch:
        check_epoch -= 1
        shard = (
            shard + config.SHARD_COUNT - get_shard_delta(state, check_epoch)
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
