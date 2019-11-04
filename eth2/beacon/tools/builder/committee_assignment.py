from typing import NamedTuple, Tuple

from eth_utils import ValidationError

from eth2.beacon.committee_helpers import (
    get_beacon_committee,
    get_committee_count_at_slot,
)
from eth2.beacon.exceptions import NoCommitteeAssignment
from eth2.beacon.helpers import compute_start_slot_at_epoch
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import CommitteeIndex, Epoch, Slot, ValidatorIndex
from eth2.configs import CommitteeConfig, Eth2Config

CommitteeAssignment = NamedTuple(
    "CommitteeAssignment",
    (
        ("committee", Tuple[ValidatorIndex, ...]),
        ("committee_index", CommitteeIndex),
        ("slot", Slot),
    ),
)


# TODO(ralexstokes) refactor using other helpers, also likely to have duplicated in tests
def get_committee_assignment(
    state: BeaconState,
    config: Eth2Config,
    epoch: Epoch,
    validator_index: ValidatorIndex,
) -> CommitteeAssignment:
    """
    Return the ``CommitteeAssignment`` in the ``epoch`` for ``validator_index``.
    ``CommitteeAssignment.committee`` is the tuple array of validators in the committee
    ``CommitteeAssignment.index`` is the index to which the committee is assigned
    ``CommitteeAssignment.slot`` is the slot at which the committee is assigned
    """
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    if epoch > next_epoch:
        raise ValidationError(
            f"Epoch for committee assignment ({epoch}) must not be after next epoch {next_epoch}."
        )

    epoch_start_slot = compute_start_slot_at_epoch(epoch, config.SLOTS_PER_EPOCH)

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        committees_at_slot = get_committee_count_at_slot(
            state,
            Slot(slot),
            config.MAX_COMMITTEES_PER_SLOT,
            config.SLOTS_PER_EPOCH,
            config.TARGET_COMMITTEE_SIZE,
        )
        for committee_index in range(committees_at_slot):
            committee = get_beacon_committee(
                state, slot, committee_index, CommitteeConfig(config)
            )
            if validator_index in committee:
                return CommitteeAssignment(
                    committee, CommitteeIndex(committee_index), Slot(slot)
                )

    raise NoCommitteeAssignment
