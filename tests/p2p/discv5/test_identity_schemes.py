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
    default_identity_scheme_registry,
    IdentityScheme,
    V4IdentityScheme,
)
from p2p.discv5.enr import (
    UnsignedENR,
    ENR,
)


def test_default_registry_contents():
    identity_schemes = tuple(
        member for _, member in inspect.getmembers(identity_schemes_module)
        if (
            inspect.isclass(member) and
            issubclass(member, IdentityScheme) and
            member is not IdentityScheme
        )
    )

    assert len(identity_schemes) == len(default_identity_scheme_registry)
    for identity_scheme in identity_schemes:
        assert identity_scheme.id in default_identity_scheme_registry
        assert default_identity_scheme_registry[identity_scheme.id] is identity_scheme


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
    signature = V4IdentityScheme.create_enr_signature(unsigned_enr, private_key.to_bytes())

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

    V4IdentityScheme.validate_enr_signature(enr)

    forged_enr = ENR(enr.sequence_number, dict(enr), b"\x00" * 64)
    with pytest.raises(ValidationError):
        V4IdentityScheme.validate_enr_signature(forged_enr)


def test_enr_public_key():
    private_key = PrivateKey(b"\x11" * 32)
    public_key = private_key.public_key.to_compressed_bytes()
    unsigned_enr = UnsignedENR(0, {
        b"id": b"v4",
        b"secp256k1": public_key,
        b"key1": b"value1",
    })
    enr = unsigned_enr.to_signed_enr(private_key.to_bytes())

    assert V4IdentityScheme.extract_public_key(unsigned_enr) == public_key
    assert V4IdentityScheme.extract_public_key(enr) == public_key


def test_enr_node_id():
    private_key = PrivateKey(b"\x11" * 32)
    unsigned_enr = UnsignedENR(0, {
        b"id": b"v4",
        b"secp256k1": private_key.public_key.to_compressed_bytes(),
        b"key1": b"value1",
    })
    enr = unsigned_enr.to_signed_enr(private_key.to_bytes())

    node_id = V4IdentityScheme.extract_node_id(enr)
    assert node_id == keccak(private_key.public_key.to_compressed_bytes())
