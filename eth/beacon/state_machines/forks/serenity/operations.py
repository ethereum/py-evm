from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState
from eth.beacon.state_machines.configs import BeaconConfig


def process_attestations(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: BeaconConfig) -> BeaconState:
    # TODO
    # It's just for demo!!!
    state = state.copy(
        slot=config.ZERO_BALANCE_VALIDATOR_TTL,
    )
    return state
