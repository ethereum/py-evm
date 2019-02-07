import pytest

import rlp

from eth2.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth2.beacon.types.slashable_attestations import (
    SlashableAttestation,
)


def test_defaults(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    assert (slashable_attestation.validator_indices ==
            sample_slashable_attestation_params['validator_indices'])
    assert (slashable_attestation.custody_bitfield ==
            sample_slashable_attestation_params['custody_bitfield'])
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


@pytest.mark.parametrize(
    (
        'custody_bitfield',
        'is_custody_bitfield_empty'
    ),
    [
        (b'\x00\x00', True),
        (b'\x00\x01', False),
    ],
)
def test_is_custody_bitfield_empty(sample_slashable_attestation_params,
                                   custody_bitfield,
                                   is_custody_bitfield_empty):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params).copy(
        custody_bitfield=custody_bitfield,
    )
    assert slashable_attestation.is_custody_bitfield_empty == is_custody_bitfield_empty


@pytest.mark.parametrize(
    (
        'validator_indices',
        'is_validator_indices_ascending'
    ),
    [
        ((0, 1, 2), True),
        ((0, 2, 1), False),
    ],
)
def test_is_validator_indices_ascending(
        sample_slashable_attestation_params,
        validator_indices,
        is_validator_indices_ascending):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params).copy(
        validator_indices=validator_indices,
    )
    assert slashable_attestation.is_validator_indices_ascending == is_validator_indices_ascending


@pytest.mark.parametrize(
    (
        'validator_indices',
        'custody_bitfield',
        'custody_bit_indices'
    ),
    [
        ((0, 1, 2), b'\x80', ((1, 2), (0,))),
        ((0, 1, 2), b'\xC0', ((2,), (0, 1))),
    ],
)
def test_custody_bit_indices(
        sample_slashable_attestation_params,
        validator_indices,
        custody_bitfield,
        custody_bit_indices):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params).copy(
        validator_indices=validator_indices,
        custody_bitfield=custody_bitfield,
    )
    assert slashable_attestation.custody_bit_indices == custody_bit_indices


def test_messages(sample_slashable_attestation_params):
    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)

    assert slashable_attestation.messages == (
        AttestationDataAndCustodyBit(slashable_attestation.data, False).root,
        AttestationDataAndCustodyBit(slashable_attestation.data, True).root,
    )
