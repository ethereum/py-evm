from typing import NamedTuple, Tuple

from eth_utils import ValidationError

from eth2.beacon.committee_helpers import iterate_committees_at_epoch
from eth2.beacon.exceptions import NoCommitteeAssignment
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
    ``CommitteeAssignment.committee_index`` is the index to which the committee is assigned
    ``CommitteeAssignment.slot`` is the slot at which the committee is assigned
    """
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    if epoch > next_epoch:
        raise ValidationError(
            f"Epoch for committee assignment ({epoch}) must not be after next epoch {next_epoch}."
        )

    for committee, committee_index, slot in iterate_committees_at_epoch(
        state, epoch, CommitteeConfig(config)
    ):
        if validator_index in committee:
            return CommitteeAssignment(
                committee, CommitteeIndex(committee_index), Slot(slot)
            )

    raise NoCommitteeAssignment
