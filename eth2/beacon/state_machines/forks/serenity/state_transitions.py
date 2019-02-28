from eth_typing import (
    Hash32,
)

from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.state_machines.state_transitions import BaseStateTransition
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState

from .block_processing import (
    process_eth1_data,
)
from .block_validation import (
    validate_block_slot,
    validate_proposer_signature,
)
from .epoch_processing import (
    process_justification,
    process_crosslinks,
    process_final_updates,
    process_rewards_and_penalties,
    process_validator_registry,
)
from .operation_processing import (
    process_attestations,
    process_attester_slashings,
    process_proposer_slashings,
)
from .slot_processing import (
    process_slot_transition,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: BeaconConfig):
        self.config = config

    def apply_state_transition(self,
                               state: BeaconState,
                               block: BaseBeaconBlock,
                               check_proposer_signature: bool=True) -> BeaconState:
        while state.slot != block.slot:
            state = self.per_slot_transition(state, block.parent_root)
            if state.slot == block.slot:
                state = self.per_block_transition(state, block, check_proposer_signature)
            if (state.slot + 1) % self.config.SLOTS_PER_EPOCH == 0:
                state = self.per_epoch_transition(state, block)

        return state

    def per_slot_transition(self,
                            state: BeaconState,
                            previous_block_root: Hash32) -> BeaconState:
        return process_slot_transition(state, self.config, previous_block_root)

    def per_block_transition(self,
                             state: BeaconState,
                             block: BaseBeaconBlock,
                             check_proposer_signature: bool=True) -> BeaconState:
        validate_block_slot(state, block)

        if check_proposer_signature:
            validate_proposer_signature(
                state,
                block,
                beacon_chain_shard_number=self.config.BEACON_CHAIN_SHARD_NUMBER,
                committee_config=CommitteeConfig(self.config),
            )

        # TODO: state = process_randao(state, block, self.config)
        state = process_eth1_data(state, block)

        # Operations
        state = process_proposer_slashings(state, block, self.config)
        state = process_attester_slashings(state, block, self.config)
        state = process_attestations(state, block, self.config)
        # TODO: state = process_deposits(state, block, self.config)
        # TODO: state = process_voluntary_exits(state, block, self.config)
        # TODO: state = process_transfers(state, block, self.config)

        return state

    def per_epoch_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO: state = process_eth1_data_votes(state, self.config)
        state = process_justification(state, self.config)
        state = process_crosslinks(state, self.config)
        state = process_rewards_and_penalties(state, self.config)
        # TODO: state = process_ejections(state, self.config)
        state = process_validator_registry(state, self.config)
        state = process_final_updates(state, self.config)

        return state
