import rlp
from eth2.beacon.types.attester_slashings import AttesterSlashing


def test_defaults(sample_attester_slashing_params):
    attester_slashing = AttesterSlashing(**sample_attester_slashing_params)

    assert (
        attester_slashing.slashable_attestation_1.validator_indices ==
        sample_attester_slashing_params['slashable_attestation_1'].validator_indices
    )
    assert (
        attester_slashing.slashable_attestation_2.custody_bitfield ==
        sample_attester_slashing_params['slashable_attestation_2'].custody_bitfield
    )

    assert rlp.encode(attester_slashing)
