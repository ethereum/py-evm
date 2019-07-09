from typing import (
    Tuple,
    NamedTuple,
)

from eth_utils import (
    ValidationError,
)

from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_crosslink_committee,
    get_epoch_committee_count,
    get_epoch_start_shard,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_epoch_start_slot,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Shard,
    Slot,
    ValidatorIndex,
    Epoch,
)
from eth2.beacon.exceptions import (
    NoCommitteeAssignment,
)


CommitteeAssignment = NamedTuple(
    'CommitteeAssignment',
    (
        ('committee', Tuple[ValidatorIndex, ...]),
        ('shard', Shard),
        ('slot', Slot),
        ('is_proposer', bool)
    )
)


# TODO(ralexstokes) refactor using other helpers, also likely to have duplicated in tests
def get_committee_assignment(state: BeaconState,
                             config: Eth2Config,
                             epoch: Epoch,
                             validator_index: ValidatorIndex) -> CommitteeAssignment:
    """
    Return the ``CommitteeAssignment`` in the ``epoch`` for ``validator_index``.
    ``CommitteeAssignment.committee`` is the tuple array of validators in the committee
    ``CommitteeAssignment.shard`` is the shard to which the committee is assigned
    ``CommitteeAssignment.slot`` is the slot at which the committee is assigned
    ``CommitteeAssignment.is_proposer`` is a bool signalling if the validator is expected to
        propose a beacon block at the assigned slot.
    """
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    if epoch > next_epoch:
        raise ValidationError(
            f"Epoch for committee assignment ({epoch}) must not be after next epoch {next_epoch}."
        )

    active_validators = get_active_validator_indices(state.validators, epoch)
    committees_per_slot = get_epoch_committee_count(
        len(active_validators),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    ) // config.SLOTS_PER_EPOCH
    epoch_start_slot = get_epoch_start_slot(
        epoch,
        config.SLOTS_PER_EPOCH,
    )
    epoch_start_shard = get_epoch_start_shard(state, epoch, CommitteeConfig(config))

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        offset = committees_per_slot * (slot % config.SLOTS_PER_EPOCH)
        slot_start_shard = (epoch_start_shard + offset) % config.SHARD_COUNT
        for i in range(committees_per_slot):
            shard = Shard((slot_start_shard + i) % config.SHARD_COUNT)
            committee = get_crosslink_committee(state, epoch, shard, CommitteeConfig(config))
            if validator_index in committee:
                is_proposer = validator_index == get_beacon_proposer_index(
                    state.copy(
                        slot=slot,
                    ),
                    CommitteeConfig(config),
                )
                return CommitteeAssignment(committee, Shard(shard), Slot(slot), is_proposer)

    raise NoCommitteeAssignment
