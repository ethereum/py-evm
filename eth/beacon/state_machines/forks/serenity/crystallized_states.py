from eth.beacon.types.crystallized_states import CrystallizedState


class SerenityCrystallizedState(CrystallizedState):
    @classmethod
    def from_crystallized_state(cls,
                                crystallized_state: CrystallizedState
                                ) -> "SerenityCrystallizedState":
        return cls(
            validators=crystallized_state.validators,
            last_state_recalc=crystallized_state.last_state_recalc,
            shard_and_committee_for_slots=crystallized_state.shard_and_committee_for_slots,
            last_justified_slot=crystallized_state.last_justified_slot,
            justified_streak=crystallized_state.justified_streak,
            last_finalized_slot=crystallized_state.last_finalized_slot,
            current_dynasty=crystallized_state.current_dynasty,
            crosslink_records=crystallized_state.crosslink_records,
            dynasty_seed=crystallized_state.dynasty_seed,
            dynasty_start=crystallized_state.dynasty_start,
        )
