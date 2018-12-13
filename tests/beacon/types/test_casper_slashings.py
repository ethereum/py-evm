from eth.beacon.types.casper_slashings import CasperSlashing


def test_defaults(sample_casper_slashing_params):
    slashing = CasperSlashing(**sample_casper_slashing_params)

    assert (slashing.slashable_vote_data_1
            .aggregate_signature_poc_0_indices ==
            sample_casper_slashing_params['slashable_vote_data_1']
            .aggregate_signature_poc_0_indices
            )
    assert (slashing.slashable_vote_data_2
            .aggregate_signature_poc_1_indices ==
            sample_casper_slashing_params['slashable_vote_data_2']
            .aggregate_signature_poc_1_indices
            )
