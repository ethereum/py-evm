import pytest

from eth2.beacon.types.eth1_data_vote import Eth1DataVote
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BeaconBlock

from eth2.beacon.state_machines.forks.serenity.block_processing import (
    process_eth1_data,
)

HASH1 = b"\x11" * 32
HASH2 = b"\x22" * 32


@pytest.mark.parametrize(("original_votes", "block_data", "expected_votes"), (
    ((), HASH1, ((HASH1, 1),)),
    (((HASH1, 5),), HASH1, ((HASH1, 6),)),
    (((HASH2, 5),), HASH1, ((HASH2, 5), (HASH1, 1))),
    (((HASH1, 10), (HASH2, 2)), HASH2, ((HASH1, 10), (HASH2, 3))),
))
def test_process_eth1_data(original_votes,
                           block_data,
                           expected_votes,
                           sample_beacon_state_params,
                           sample_beacon_block_params,
                           config):
    eth1_data_votes = tuple(
        Eth1DataVote(data, vote_count)
        for data, vote_count in original_votes
    )
    state = BeaconState(**sample_beacon_state_params).copy(
        eth1_data_votes=eth1_data_votes,
    )

    block = BeaconBlock(**sample_beacon_block_params).copy(
        eth1_data=block_data,
    )

    updated_state = process_eth1_data(state, block, config)
    updated_votes = tuple(
        (vote.eth1_data, vote.vote_count)
        for vote in updated_state.eth1_data_votes
    )
    assert updated_votes == expected_votes
