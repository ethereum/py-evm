import pytest

from evm.utils.keccak import keccak
from evm.utils.secp256k1 import (
    decode_public_key,
    encode_raw_public_key,
)
from evm.utils.ecdsa import (
    encode_signature,
    decode_signature,
    ecdsa_verify_address,
)
from tests.ecdsa_fixtures import (
    MSG,
    SECRETS,
)


@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_encode_decode_raw_public_key(label, d):
    assert encode_raw_public_key(decode_public_key(d['pubkey'])) == d['pubkey']


@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_signature_encoding_and_decoding(label, d):
    v, r, s, = decode_signature(d['sig'])
    assert (v, r, s) == d['raw_sig']
    assert encode_signature(v, r, s) == d['sig']


@pytest.mark.parametrize("label, d", sorted(SECRETS.items()))
def test_verify_address(label, d):
    addr = keccak(d['pubkey'])[-20:]
    assert ecdsa_verify_address(MSG, d['sig'], addr)
