from eth2.beacon.types.proposal import (
    Proposal,
)


def test_defaults(sample_proposal_params):
    proposal = Proposal(**sample_proposal_params)
    assert proposal.slot == sample_proposal_params['slot']
    assert proposal.shard == sample_proposal_params['shard']
    assert proposal.block_root == sample_proposal_params['block_root']
