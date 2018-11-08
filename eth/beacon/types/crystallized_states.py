from typing import (
    Iterable,
    Tuple,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    int64,
    hash32,
)
from eth.utils.blake import (
    blake,
)
from eth.beacon.helpers import (
    get_active_validator_indices,
)

from .crosslink_records import CrosslinkRecord
from .shard_and_committees import ShardAndCommittee
from .validator_records import ValidatorRecord


class CrystallizedState(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # List of validators
        ('validators', CountableList(ValidatorRecord)),
        # Last CrystallizedState recalculation
        ('last_state_recalc', int64),
        # What active validators are part of the attester set
        # at what height, and in what shard. Starts at slot
        # last_state_recalc - CYCLE_LENGTH
        ('shard_and_committee_for_slots', CountableList(CountableList(ShardAndCommittee))),
        # The last justified slot
        ('last_justified_slot', int64),
        # Number of consecutive justified slots ending at this one
        ('justified_streak', int64),
        # The last finalized slot
        ('last_finalized_slot', int64),
        # The current dynasty
        ('current_dynasty', int64),
        # Records about the most recent crosslink for each shard
        ('crosslink_records', CountableList(CrosslinkRecord)),
        # Used to select the committees for each shard
        ('dynasty_seed', hash32),
        # start of the current dynasty
        ('dynasty_start', int64),
    ]

    def __init__(self,
                 validators: Iterable[ValidatorRecord],
                 last_state_recalc: int,
                 shard_and_committee_for_slots: Iterable[Iterable[ShardAndCommittee]],
                 last_justified_slot: int,
                 justified_streak: int,
                 last_finalized_slot: int,
                 current_dynasty: int,
                 crosslink_records: Iterable[CrosslinkRecord],
                 dynasty_seed: Hash32,
                 dynasty_start: int) -> None:

        super().__init__(
            validators=validators,
            last_state_recalc=last_state_recalc,
            shard_and_committee_for_slots=shard_and_committee_for_slots,
            last_justified_slot=last_justified_slot,
            justified_streak=justified_streak,
            last_finalized_slot=last_finalized_slot,
            current_dynasty=current_dynasty,
            crosslink_records=crosslink_records,
            dynasty_seed=dynasty_seed,
            dynasty_start=dynasty_start,
        )

    def __repr__(self) -> str:
        return '<CrystallizedState #{0}>'.format(
            encode_hex(self.hash)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = blake(rlp.encode(self))
        return self._hash

    @property
    def active_validator_indices(self) -> Tuple[int]:
        return get_active_validator_indices(
            self.current_dynasty,
            self.validators
        )

    @property
    def total_balance(self) -> int:
        return sum(
            self.validators[index].balance
            for index in self.active_validator_indices
        )

    @property
    def num_validators(self) -> int:
        return len(self.validators)

    @property
    def num_crosslink_records(self) -> int:
        return len(self.crosslink_records)
