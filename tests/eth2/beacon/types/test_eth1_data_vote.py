from eth2.beacon.types.eth1_data_vote import (
    Eth1DataVote,
)


def test_defaults(sample_eth1_data_vote_params):
    eth1_data_vote = Eth1DataVote(
        **sample_eth1_data_vote_params,
    )
    assert eth1_data_vote.eth1_data == sample_eth1_data_vote_params['eth1_data']
    assert eth1_data_vote.vote_count == sample_eth1_data_vote_params['vote_count']
