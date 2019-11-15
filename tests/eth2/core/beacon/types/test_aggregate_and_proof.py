from eth2.beacon.types.aggregate_and_proof import AggregateAndProof


def test_defaults(sample_aggregate_and_proof_params):
    aggregate_and_proof = AggregateAndProof(**sample_aggregate_and_proof_params)

    assert aggregate_and_proof.index == sample_aggregate_and_proof_params["index"]
    assert (
        aggregate_and_proof.selection_proof
        == sample_aggregate_and_proof_params["selection_proof"]
    )
    assert (
        aggregate_and_proof.aggregate == sample_aggregate_and_proof_params["aggregate"]
    )
