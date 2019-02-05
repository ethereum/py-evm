import rlp

from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth2.beacon.types.slashable_attestations import (
    SlashableAttestation,
)


def test_defaults(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    assert (slashable_attestation.custody_bit_0_indices ==
            sample_slashable_attestation_params['custody_bit_0_indices'])
    assert (slashable_attestation.custody_bit_1_indices ==
            sample_slashable_attestation_params['custody_bit_1_indices'])
    assert slashable_attestation.data == sample_slashable_attestation_params['data']
    assert (
        slashable_attestation.aggregate_signature ==
        sample_slashable_attestation_params['aggregate_signature']
    )
    assert rlp.encode(slashable_attestation)


def test_hash(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    # NOTE: this hash was simply copied from the existing implementation
    # which should be the keccak-256 of the rlp serialization of `votes`.
    # Given that this value will change soon (cf. ssz tree hash), we just
    # do this to get the test passing for now and will need to update later
    # if we expect the hash computation is not working correctly
    hash_hex = "0748b74fa43b72cb0afa29b803113d6ca921d98ec6feffecb9962af47d477d2a"

    assert slashable_attestation.hash == bytes.fromhex(hash_hex)


def test_root(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    # NOTE: see note in `test_hash`, this test will need to be updated
    # once ssz tree hash lands...

    assert slashable_attestation.root == slashable_attestation.hash


def test_vote_count(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    key = "custody_bit_0_indices"
    custody_bit_0_indices = sample_slashable_attestation_params[key]
    key = "custody_bit_1_indices"
    custody_bit_1_indices = sample_slashable_attestation_params[key]

    assert slashable_attestation.vote_count == (
        len(custody_bit_0_indices) + len(custody_bit_1_indices)
    )


def test_messages(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    assert slashable_attestation.messages == (
        AttestationDataAndCustodyBit(slashable_attestation.data, False).root,
        AttestationDataAndCustodyBit(slashable_attestation.data, True).root,
    )
