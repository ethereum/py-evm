import pytest

from evm.utils.secp256k1 import (
    private_key_to_public_key,
)

from tests.ecdsa_fixtures import SECRETS


@pytest.mark.parametrize('label, d', sorted(SECRETS.items()))
def test_private_key_to_public_key(label, d):
    actual = private_key_to_public_key(d['privkey'])
    assert actual == d['pubkey']
