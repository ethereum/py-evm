import base64

import pytest

import rlp

from eth_utils import (
    decode_hex,
    ValidationError,
)
from eth_utils.toolz import (
    assoc,
    assoc_in,
)

from p2p.discv5.enr import (
    ENR,
    ENRSedes,
    UnsignedENR,
)
from p2p.discv5.identity_schemes import (
    IdentityScheme,
    V4IdentityScheme,
    IdentitySchemeRegistry,
)


# Source: https://github.com/fjl/EIPs/blob/0acb5939555cbd0efcdd04da0d3acb0cc81d049a/EIPS/eip-778.md
OFFICIAL_TEST_DATA = {
    "repr": (
        "enr:-IS4QHCYrYZbAKWCBRlAy5zzaDZXJBGkcnh4MHcBFZntXNFrdvJjX04jRzjzCBOonrkT"
        "fj499SZuOh8R33Ls8RRcy5wBgmlkgnY0gmlwhH8AAAGJc2VjcDI1NmsxoQPKY0yuDUmstAHY"
        "pMa2_oxVtw0RW_QAdpzBQA8yWM0xOIN1ZHCCdl8"
    ),
    "private_key": decode_hex("b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"),
    "public_key": decode_hex("03ca634cae0d49acb401d8a4c6b6fe8c55b70d115bf400769cc1400f3258cd3138"),
    "node_id": decode_hex("a448f24c6d18e575453db13171562b71999873db5b286df957af199ec94617f7"),
    "identity_scheme": V4IdentityScheme,
    "sequence_number": 1,
    "kv_pairs": {
        b"id": b"v4",
        b"ip": decode_hex("7f000001"),
        b"secp256k1": decode_hex(
            "03ca634cae0d49acb401d8a4c6b6fe8c55b70d115bf400769cc1400f3258cd3138",
        ),
        b"udp": 0x765f,
    }
}


class MockIdentityScheme(IdentityScheme):

    id = b"mock"
    private_key_size = 32

    @classmethod
    def create_enr_signature(cls, enr, private_key: bytes) -> bytes:
        if len(private_key) != cls.private_key_size:
            raise ValidationError("Invalid private key")
        return private_key + enr.get_signing_message()

    @classmethod
    def validate_enr_structure(cls, enr) -> None:
        pass

    @classmethod
    def validate_enr_signature(cls, enr) -> None:
        if not enr.signature == enr.node_id + enr.get_signing_message():
            raise ValidationError("Invalid signature")

    @classmethod
    def extract_public_key(cls, enr) -> bytes:
        return b""

    @classmethod
    def extract_node_id(cls, enr) -> bytes:
        return enr.signature[:cls.private_key_size]


@pytest.fixture
def mock_identity_scheme():
    return MockIdentityScheme


@pytest.fixture
def identity_scheme_registry(mock_identity_scheme):
    registry = IdentitySchemeRegistry()
    registry.register(V4IdentityScheme)
    registry.register(mock_identity_scheme)
    return registry


def test_mapping_interface(identity_scheme_registry):
    kv_pairs = {
        b"id": b"mock",
        b"key1": b"value1",
        b"key2": b"value2",
    }
    enr = ENR(
        signature=b"",
        sequence_number=0,
        kv_pairs=kv_pairs,
        identity_scheme_registry=identity_scheme_registry,
    )

    for key, value in kv_pairs.items():
        assert key in enr
        assert enr[key] == value
        assert enr.get(key) == value

    not_a_key = b"key3"
    assert not_a_key not in kv_pairs
    assert not_a_key not in enr
    enr.get(not_a_key) is None
    assert enr.get(not_a_key, b"default") == b"default"

    assert tuple(enr.keys()) == tuple(kv_pairs.keys())
    assert tuple(enr.values()) == tuple(kv_pairs.values())
    assert tuple(enr.items()) == tuple(kv_pairs.items())

    assert len(enr) == len(kv_pairs)

    assert tuple(iter(enr)) == tuple(iter(kv_pairs))


def test_inititialization(identity_scheme_registry):
    valid_sequence_number = 0
    valid_kv_pairs = {b"id": b"mock"}
    valid_signature = b""  # signature is not validated during initialization

    assert UnsignedENR(
        sequence_number=valid_sequence_number,
        kv_pairs=valid_kv_pairs,
        identity_scheme_registry=identity_scheme_registry,
    )
    assert ENR(
        sequence_number=valid_sequence_number,
        kv_pairs=valid_kv_pairs,
        signature=valid_signature,
        identity_scheme_registry=identity_scheme_registry,
    )

    with pytest.raises(ValidationError):
        UnsignedENR(
            sequence_number=valid_sequence_number,
            kv_pairs={b"no-id": b""},
            identity_scheme_registry=identity_scheme_registry,
        )
    with pytest.raises(ValidationError):
        ENR(
            sequence_number=valid_sequence_number,
            kv_pairs={b"no-id": b""},
            signature=valid_signature,
            identity_scheme_registry=identity_scheme_registry,
        )

    with pytest.raises(ValidationError):
        UnsignedENR(
            sequence_number=-1,
            kv_pairs=valid_kv_pairs,
            identity_scheme_registry=identity_scheme_registry,
        )
    with pytest.raises(ValidationError):
        ENR(
            sequence_number=-1,
            kv_pairs=valid_kv_pairs,
            signature=valid_signature,
            identity_scheme_registry=identity_scheme_registry,
        )


def test_signing(mock_identity_scheme, identity_scheme_registry):
    unsigned_enr = UnsignedENR(
        sequence_number=0,
        kv_pairs={b"id": b"mock"},
        identity_scheme_registry=identity_scheme_registry
    )
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    assert enr.signature == mock_identity_scheme.create_enr_signature(enr, private_key)


def test_signature_validation(mock_identity_scheme, identity_scheme_registry):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"}, identity_scheme_registry)
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    enr.validate_signature()

    invalid_signature = b"\xff" * 64
    invalid_enr = ENR(
        enr.sequence_number,
        dict(enr),
        invalid_signature,
        identity_scheme_registry=identity_scheme_registry
    )
    with pytest.raises(ValidationError):
        invalid_enr.validate_signature()

    with pytest.raises(ValidationError):
        ENR(
            0,
            {b"id": b"unknown"},
            b"",
            identity_scheme_registry=identity_scheme_registry,
        )


def test_public_key(mock_identity_scheme, identity_scheme_registry):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"}, identity_scheme_registry)
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    assert enr.public_key == mock_identity_scheme.extract_public_key(enr)


def test_node_id(mock_identity_scheme, identity_scheme_registry):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"}, identity_scheme_registry)
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    assert enr.node_id == private_key


def test_signature_scheme_selection(mock_identity_scheme, identity_scheme_registry):
    mock_enr = ENR(0, {b"id": b"mock"}, b"", identity_scheme_registry)
    assert mock_enr.identity_scheme is mock_identity_scheme

    v4_enr = ENR(0, {b"id": b"v4", b"secp256k1": b"\x02" * 33}, b"", identity_scheme_registry)
    assert v4_enr.identity_scheme is V4IdentityScheme

    with pytest.raises(ValidationError):
        ENR(0, {b"id": b"other"}, b"", identity_scheme_registry)


def test_repr(mock_identity_scheme, identity_scheme_registry):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"}, identity_scheme_registry)
    enr = unsigned_enr.to_signed_enr(b"\x00" * 32)
    base64_encoded_enr = base64.urlsafe_b64encode(rlp.encode(enr))
    represented_enr = repr(enr)

    assert represented_enr.startswith("enr:")
    assert base64_encoded_enr.rstrip(b"=").decode() == represented_enr[4:]

    assert ENR.from_repr(represented_enr, identity_scheme_registry) == enr


def test_deserialization_key_order_validation(identity_scheme_registry):
    serialized_enr = rlp.encode([
        b"signature",
        0,
        b"key1",
        b"value1",
        b"id",
        b"",
        b"key2",
        b"value2",
    ])
    with pytest.raises(rlp.DeserializationError):
        rlp.decode(
            serialized_enr,
            ENRSedes,
            identity_scheme_registry=identity_scheme_registry,
        )


def test_deserialization_key_uniqueness_validation(identity_scheme_registry):
    serialized_enr = rlp.encode([
        b"signature",
        0,
        b"key1",
        b"value1",
        b"id",
        b"",
        b"key1",
        b"value2",
    ])
    with pytest.raises(rlp.DeserializationError):
        rlp.decode(
            serialized_enr,
            ENRSedes,
            identity_scheme_registry=identity_scheme_registry,
        )


@pytest.mark.parametrize("incomplete_enr", (
    (),
    (b"signature",),
    (b"signature", 0, b"key1"),
    (b"signature", 0, b"key1", b"value1", b"id"),
))
def test_deserialization_completeness_validation(incomplete_enr, identity_scheme_registry):
    incomplete_enr_rlp = rlp.encode(incomplete_enr)
    with pytest.raises(rlp.DeserializationError):
        rlp.decode(
            incomplete_enr_rlp,
            ENRSedes,
            identity_scheme_registry=identity_scheme_registry,
        )


def test_equality(identity_scheme_registry):
    base_kwargs = {
        "sequence_number": 0,
        "kv_pairs": {
            b"id": b"mock",
            b"key1": b"value1",
            b"key2": b"value2",
        },
        "signature": b"signature",
        "identity_scheme_registry": identity_scheme_registry,
    }

    base_enr = ENR(**base_kwargs)
    equal_enr = ENR(**base_kwargs)
    enr_different_sequence_number = ENR(
        **assoc(base_kwargs, "sequence_number", 1)
    )
    enr_different_kv_pairs = ENR(
        **assoc_in(base_kwargs, ("kv_pairs", b"key1"), b"value2"),
    )
    enr_different_signature = ENR(
        **assoc(base_kwargs, "signature", b"different-signature")
    )

    assert base_enr == base_enr
    assert equal_enr == base_enr
    assert enr_different_sequence_number != base_enr
    assert enr_different_kv_pairs != base_enr
    assert enr_different_signature != base_enr


def test_serialization_roundtrip(identity_scheme_registry):
    original_enr = ENR(
        sequence_number=0,
        kv_pairs={
            b"id": b"mock",
            b"key2": b"value2",  # wrong order so that serialization is forced to fix this
            b"key1": b"value1",
        },
        signature=b"",
        identity_scheme_registry=identity_scheme_registry,
    )
    encoded = rlp.encode(original_enr)
    recovered_enr = rlp.decode(
        encoded,
        ENR,
        identity_scheme_registry=identity_scheme_registry,
    )
    assert recovered_enr == original_enr


@pytest.mark.parametrize("invalid_kv_pairs", (
    {b"id": b"v4"},  # missing public key
    {b"id": b"v4", b"secp256k1": b"\x00"},  # invalid public key
))
def test_v4_structure_validation(invalid_kv_pairs, identity_scheme_registry):
    with pytest.raises(ValidationError):
        UnsignedENR(
            sequence_number=0,
            kv_pairs=invalid_kv_pairs,
            identity_scheme_registry=identity_scheme_registry,
        )


def test_official_test_vector():
    enr = ENR.from_repr(OFFICIAL_TEST_DATA["repr"])  # use default identity scheme registry

    assert enr.sequence_number == OFFICIAL_TEST_DATA["sequence_number"]
    assert dict(enr) == OFFICIAL_TEST_DATA["kv_pairs"]
    assert enr.public_key == OFFICIAL_TEST_DATA["public_key"]
    assert enr.node_id == OFFICIAL_TEST_DATA["node_id"]
    assert enr.identity_scheme is OFFICIAL_TEST_DATA["identity_scheme"]
    assert repr(enr) == OFFICIAL_TEST_DATA["repr"]

    unsigned_enr = UnsignedENR(enr.sequence_number, dict(enr))
    reconstructed_enr = unsigned_enr.to_signed_enr(OFFICIAL_TEST_DATA["private_key"])
    assert reconstructed_enr == enr
