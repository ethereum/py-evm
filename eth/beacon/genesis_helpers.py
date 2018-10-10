from typing import (
    Sequence,
    TYPE_CHECKING,
)

from eth_typing import (
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.types.active_states import ActiveState
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.crosslink_records import CrosslinkRecord
from eth.beacon.types.crystallized_states import CrystallizedState
from eth.beacon.helpers import (
    get_new_shuffling,
)

if TYPE_CHECKING:
    from eth.beacon.types.validator_records import ValidatorRecord  # noqa: F401


def get_genesis_active_state(cycle_length: int) -> ActiveState:
    recent_block_hashes = [ZERO_HASH32] * cycle_length * 2

    return ActiveState(
        pending_attestations=[],
        recent_block_hashes=recent_block_hashes,
    )


def get_genesis_crystallized_state(
        validators: Sequence['ValidatorRecord'],
        init_shuffling_seed: Hash32,
        cycle_length: int,
        min_committee_size: int,
        shard_count: int) -> CrystallizedState:

    current_dynasty = 1
    crosslinking_start_shard = 0

    shard_and_committee_for_slots = get_new_shuffling(
        seed=init_shuffling_seed,
        validators=validators,
        dynasty=current_dynasty,
        crosslinking_start_shard=crosslinking_start_shard,
        cycle_length=cycle_length,
        min_committee_size=min_committee_size,
        shard_count=shard_count,
    )
    # concatenate with itself to span 2*CYCLE_LENGTH
    shard_and_committee_for_slots = shard_and_committee_for_slots + shard_and_committee_for_slots

    return CrystallizedState(
        validators=validators,
        last_state_recalc=0,
        shard_and_committee_for_slots=shard_and_committee_for_slots,
        last_justified_slot=0,
        justified_streak=0,
        last_finalized_slot=0,
        current_dynasty=current_dynasty,
        crosslink_records=[
            CrosslinkRecord(
                dynasty=0,
                slot=0,
                hash=ZERO_HASH32,
            )
            for _ in range(shard_count)
        ],
        dynasty_seed=init_shuffling_seed,
        dynasty_start=0,
    )


def get_genesis_block(active_state_root: Hash32,
                      crystallized_state_root: Hash32) -> BaseBeaconBlock:
    return BaseBeaconBlock(
        parent_hash=ZERO_HASH32,
        slot_number=0,
        randao_reveal=ZERO_HASH32,
        attestations=[],
        pow_chain_ref=ZERO_HASH32,
        active_state_root=active_state_root,
        crystallized_state_root=crystallized_state_root,
    )
