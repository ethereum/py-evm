from eth.beacon.types.casper_slashings import CasperSlashing


def test_defaults(sample_casper_slashing_params):
    slashing = CasperSlashing(**sample_casper_slashing_params)

    assert (slashing.votes_1.aggregate_signature_poc_0_indices ==
            sample_casper_slashing_params['votes_1'].aggregate_signature_poc_0_indices)
    assert (slashing.votes_2.aggregate_signature_poc_1_indices ==
            sample_casper_slashing_params['votes_2'].aggregate_signature_poc_1_indices)
