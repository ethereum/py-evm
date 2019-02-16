from eth_utils.toolz import (
    first,
)

from eth2._utils.tuple import update_tuple_item

from eth2.beacon.configs import BeaconConfig
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.eth1_data_vote import Eth1DataVote


def process_eth1_data(state: BeaconState,
                      block: BaseBeaconBlock,
                      config: BeaconConfig) -> BeaconState:
    try:
        vote_index, original_vote = first(
            (index, eth1_data_vote)
            for index, eth1_data_vote in enumerate(state.eth1_data_votes)
            if block.eth1_data == eth1_data_vote.eth1_data
        )
    except StopIteration:
        new_vote = Eth1DataVote(
            eth1_data=block.eth1_data,
            vote_count=1,
        )
        state = state.copy(
            eth1_data_votes=state.eth1_data_votes + (new_vote,)
        )
    else:
        updated_vote = original_vote.copy(
            vote_count=original_vote.vote_count + 1
        )
        state = state.copy(
            eth1_data_votes=update_tuple_item(state.eth1_data_votes, vote_index, updated_vote)
        )

    return state
