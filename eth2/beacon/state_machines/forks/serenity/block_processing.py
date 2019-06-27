from eth2._utils.hash import hash_eth2
from eth2._utils.tuple import update_tuple_item
from eth2._utils.numeric import (
    bitwise_xor,
)

from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.block_headers import BeaconBlockHeader

from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_randao_reveal,
)

from eth2.beacon.helpers import (
    get_randao_mix,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)

from .block_validation import (
    validate_block_slot,
    validate_block_parent_root,
    validate_proposer_signature,
    validate_proposer_is_not_slashed,
)

from .operation_processing import (
    process_operations,
)


def process_block_header(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: Eth2Config,
                         check_proposer_signature: bool) -> BeaconState:
    validate_block_slot(state, block)
    validate_block_parent_root(state, block)
    validate_proposer_is_not_slashed(
        state,
        block.signing_root,
        CommitteeConfig(config),
    )

    if check_proposer_signature:
        validate_proposer_signature(
            state,
            block,
            committee_config=CommitteeConfig(config),
        )

    return state.copy(
        latest_block_header=BeaconBlockHeader(
            slot=block.slot,
            parent_root=block.parent_root,
            body_root=block.body.root,
        ),
    )


def process_randao(state: BeaconState,
                   block: BaseBeaconBlock,
                   config: Eth2Config) -> BeaconState:
    proposer_index = get_beacon_proposer_index(
        state=state,
        committee_config=CommitteeConfig(config),
    )

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    validate_randao_reveal(
        state=state,
        proposer_index=proposer_index,
        epoch=epoch,
        randao_reveal=block.body.randao_reveal,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
    )

    randao_mix_index = epoch % config.EPOCHS_PER_HISTORICAL_VECTOR
    new_randao_mix = bitwise_xor(
        get_randao_mix(
            state=state,
            epoch=epoch,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            epochs_per_historical_vector=config.EPOCHS_PER_HISTORICAL_VECTOR,
        ),
        hash_eth2(block.body.randao_reveal),
    )

    return state.copy(
        randao_mixes=update_tuple_item(
            state.randao_mixes,
            randao_mix_index,
            new_randao_mix,
        ),
    )


def process_eth1_data(state: BeaconState,
                      block: BaseBeaconBlock,
                      config: Eth2Config) -> BeaconState:
    body = block.body

    new_eth1_data_votes = state.eth1_data_votes + (body.eth1_data,)

    new_eth1_data = state.eth1_data
    if new_eth1_data_votes.count(body.eth1_data) * 2 > config.SLOTS_PER_ETH1_VOTING_PERIOD:
        new_eth1_data = body.eth1_data

    return state.copy(
        eth1_data=new_eth1_data,
        eth1_data_votes=new_eth1_data_votes,
    )


def process_block(state: BeaconState,
                  block: BaseBeaconBlock,
                  config: Eth2Config,
                  check_proposer_signature: bool=True) -> BeaconState:
    state = process_block_header(state, block, config, check_proposer_signature)
    state = process_randao(state, block, config)
    state = process_eth1_data(state, block, config)
    state = process_operations(state, block, config)
    return state
