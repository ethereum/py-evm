import rlp
from eth2.beacon.types.attester_slashings import AttesterSlashing


def test_defaults(sample_attester_slashing_params):
    attester_slashing = AttesterSlashing(**sample_attester_slashing_params)

    assert (
        attester_slashing.slashable_attestation_1.custody_bit_0_indices ==
        sample_attester_slashing_params['slashable_attestation_1'].custody_bit_0_indices
    )
    assert (
        attester_slashing.slashable_attestation_2.custody_bit_1_indices ==
        sample_attester_slashing_params['slashable_attestation_2'].custody_bit_1_indices
    )

    assert rlp.encode(attester_slashing)
