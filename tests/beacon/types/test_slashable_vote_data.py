from eth.beacon.types.slashable_vote_data import (
    SlashableVoteData,
)


def test_defaults(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    assert (votes.aggregate_signature_poc_0_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_0_indices'])
    assert (votes.aggregate_signature_poc_1_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_1_indices'])
    assert votes.data == sample_slashable_vote_data_params['data']
    assert votes.aggregate_signature == sample_slashable_vote_data_params['aggregate_signature']
