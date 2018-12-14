
from eth.beacon.types.proposer_slashings import (
    ProposerSlashing,
)


def test_defaults(sample_proposer_slashing_params):
    slashing = ProposerSlashing(**sample_proposer_slashing_params)
    assert slashing.proposer_index == sample_proposer_slashing_params['proposer_index']
    assert slashing.proposal_data_1 == sample_proposer_slashing_params['proposal_data_1']
    assert slashing.proposal_signature_1 == sample_proposer_slashing_params['proposal_signature_1']
    assert slashing.proposal_data_2 == sample_proposer_slashing_params['proposal_data_2']
    assert slashing.proposal_signature_2 == sample_proposer_slashing_params['proposal_signature_2']
