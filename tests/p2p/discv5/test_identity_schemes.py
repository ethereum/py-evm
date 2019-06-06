import inspect

import pytest

from eth_utils import (
    keccak,
    ValidationError,
)

from eth_keys.datatypes import (
    PrivateKey,
    NonRecoverableSignature,
)

from p2p.discv5 import identity_schemes as identity_schemes_module
from p2p.discv5.identity_schemes import (
    identity_scheme_registry,
    IdentityScheme,
    V4IdentityScheme,
)
from p2p.discv5.enr import (
    UnsignedENR,
    ENR,
)


def test_identity_schemes_are_registered_properly():
    identity_schemes = tuple(
        member for _, member in inspect.getmembers(identity_schemes_module)
        if (
            inspect.isclass(member) and
            issubclass(member, IdentityScheme) and
            member is not IdentityScheme
        )
    )

    assert len(identity_schemes) == len(identity_scheme_registry)
    for identity_scheme in identity_schemes:
        assert identity_scheme.id in identity_scheme_registry
        assert identity_scheme_registry[identity_scheme.id] is identity_scheme


#
# V4 identity scheme
#
def test_enr_signing():
    private_key = PrivateKey(b"\x11" * 32)
    unsigned_enr = UnsignedENR(0, {
        b"id": b"v4",
        b"secp256k1": private_key.public_key.to_compressed_bytes(),
        b"key1": b"value1",
    })
    signature = V4IdentityScheme.create_signature(unsigned_enr, private_key.to_bytes())

    message_hash = keccak(unsigned_enr.get_signing_message())
    assert private_key.public_key.verify_msg_hash(message_hash, NonRecoverableSignature(signature))


def test_enr_signature_validation():
    private_key = PrivateKey(b"\x11" * 32)
    unsigned_enr = UnsignedENR(0, {
        b"id": b"v4",
        b"secp256k1": private_key.public_key.to_compressed_bytes(),
        b"key1": b"value1",
    })
    enr = unsigned_enr.to_signed_enr(private_key.to_bytes())

    V4IdentityScheme.validate_signature(enr)

    forged_enr = ENR(enr.sequence_number, dict(enr), b"\x00" * 64)
    with pytest.raises(ValidationError):
        V4IdentityScheme.validate_signature(forged_enr)


def test_enr_node_address():
    private_key = PrivateKey(b"\x11" * 32)
    unsigned_enr = UnsignedENR(0, {
        b"id": b"v4",
        b"secp256k1": private_key.public_key.to_compressed_bytes(),
        b"key1": b"value1",
    })
    enr = unsigned_enr.to_signed_enr(private_key.to_bytes())

    node_address = V4IdentityScheme.extract_node_address(enr)
    assert node_address == keccak(private_key.public_key.to_bytes())
