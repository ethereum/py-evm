import ssz

from eth2.beacon.types.attester_slashings import AttesterSlashing


def test_defaults(sample_attester_slashing_params):
    attester_slashing = AttesterSlashing(**sample_attester_slashing_params)

    assert (
        attester_slashing.attestation_1.attesting_indices
        == sample_attester_slashing_params["attestation_1"].attesting_indices
    )

    assert ssz.encode(attester_slashing)
