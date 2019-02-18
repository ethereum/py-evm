from eth_typing import (
    Hash32,
)

from eth2._utils.merkle import get_merkle_root
from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.state_machines.state_transitions import BaseStateTransition
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState

from .epoch_processing import (
    process_crosslinks,
    process_final_updates,
    process_validator_registry,
)
from .operation_processing import (
    process_attestations,
)
from .block_validation import (
    validate_block_slot,
    validate_proposer_signature,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: BeaconConfig):
        self.config = config

    def apply_state_transition(self,
                               state: BeaconState,
                               block: BaseBeaconBlock,
                               check_proposer_signature: bool=False) -> BeaconState:
        while state.slot != block.slot:
            state = self.per_slot_transition(state, block.parent_root)
            if state.slot == block.slot:
                state = self.per_block_transition(state, block, check_proposer_signature)
            if (state.slot + 1) % self.config.EPOCH_LENGTH == 0:
                state = self.per_epoch_transition(state, block)

        return state

    def per_slot_transition(self,
                            state: BeaconState,
                            previous_block_root: Hash32) -> BeaconState:
        LATEST_BLOCK_ROOTS_LENGTH = self.config.LATEST_BLOCK_ROOTS_LENGTH

        # Update state.slot
        state = state.copy(
            slot=state.slot + 1
        )

        # Update state.latest_block_roots
        updated_latest_block_roots = list(state.latest_block_roots)
        previous_block_root_index = (state.slot - 1) % LATEST_BLOCK_ROOTS_LENGTH
        updated_latest_block_roots[previous_block_root_index] = previous_block_root

        # Update state.batched_block_roots
        updated_batched_block_roots = state.batched_block_roots
        if state.slot % LATEST_BLOCK_ROOTS_LENGTH == 0:
            updated_batched_block_roots += (get_merkle_root(updated_latest_block_roots),)

        state = state.copy(
            latest_block_roots=tuple(updated_latest_block_roots),
            batched_block_roots=updated_batched_block_roots,
        )
        return state

    def per_block_transition(self,
                             state: BeaconState,
                             block: BaseBeaconBlock,
                             check_proposer_signature: bool=False) -> BeaconState:
        # TODO: finish per-block processing logic as the spec
        validate_block_slot(state, block)
        if not check_proposer_signature:
            validate_proposer_signature(
                state,
                block,
                beacon_chain_shard_number=self.config.BEACON_CHAIN_SHARD_NUMBER,
                committee_config=CommitteeConfig(self.config),
            )
        # TODO: state = process_randao(state, block, self.config)
        # TODO: state = process_eth1_data(state, block, self.config)

        # Operations
        # TODO: state = process_proposer_slashings(state, block, self.config)
        # TODO: state = process_attester_slashings(state, block, self.config)
        state = process_attestations(state, block, self.config)
        # TODO: state = process_deposits(state, block, self.config)
        # TODO: state = process_exits(state, block, self.config)
        # TODO: validate_custody(state, block, self.config)

        return state

    def per_epoch_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO: state = process_et1_data_votes(state, self.config)
        # TODO: state = process_justification(state, self.config)
        state = process_crosslinks(state, self.config)
        # TODO: state = process_rewards_and_penalties(state, self.config)
        # TODO: state = process_ejections(state, self.config)
        state = process_validator_registry(state, self.config)
        state = process_final_updates(state, self.config)

        return state
