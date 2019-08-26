import ssz

from eth2.beacon.types.proposer_slashings import ProposerSlashing


def test_defaults(sample_proposer_slashing_params):
    slashing = ProposerSlashing(**sample_proposer_slashing_params)
    assert slashing.proposer_index == sample_proposer_slashing_params["proposer_index"]
    assert slashing.header_1 == sample_proposer_slashing_params["header_1"]
    assert slashing.header_2 == sample_proposer_slashing_params["header_2"]
    assert ssz.encode(slashing)
