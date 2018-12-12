from eth.beacon.types.casper_slashings import (
    CasperSlashing,
    SlashableVoteData,
)


def test_defaults_for_casper_votes(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    assert (votes.aggregate_signature_poc_0_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_0_indices'])
    assert (votes.aggregate_signature_poc_1_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_1_indices'])
    assert votes.data == sample_slashable_vote_data_params['data']
    assert votes.aggregate_signature == sample_slashable_vote_data_params['aggregate_signature']


def test_defaults_for_casper_slashing(sample_casper_slashing_params):
    slashing = CasperSlashing(**sample_casper_slashing_params)

    assert (slashing.votes_1.aggregate_signature_poc_0_indices ==
            sample_casper_slashing_params['votes_1'].aggregate_signature_poc_0_indices)
    assert (slashing.votes_2.aggregate_signature_poc_1_indices ==
            sample_casper_slashing_params['votes_2'].aggregate_signature_poc_1_indices)
