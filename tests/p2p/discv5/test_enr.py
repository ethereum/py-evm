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
    identity_scheme_registry,
)


# Source: https://github.com/fjl/EIPs/blob/0acb5939555cbd0efcdd04da0d3acb0cc81d049a/EIPS/eip-778.md
OFFICIAL_TEST_DATA = {
    "repr": (
        "enr:-IS4QHCYrYZbAKWCBRlAy5zzaDZXJBGkcnh4MHcBFZntXNFrdvJjX04jRzjzCBOonrkT"
        "fj499SZuOh8R33Ls8RRcy5wBgmlkgnY0gmlwhH8AAAGJc2VjcDI1NmsxoQPKY0yuDUmstAHY"
        "pMa2_oxVtw0RW_QAdpzBQA8yWM0xOIN1ZHCCdl8"
    ),
    "private_key": decode_hex("b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"),
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
    def create_signature(cls, enr, private_key: bytes) -> bytes:
        if len(private_key) != cls.private_key_size:
            raise ValidationError("Invalid private key")
        return private_key + enr.get_signing_message()

    @classmethod
    def validate_signature(cls, enr) -> None:
        if not enr.signature == cls.extract_node_address(enr) + enr.get_signing_message():
            raise ValidationError("Invalid signature")

    @classmethod
    def extract_node_address(cls, enr) -> bytes:
        return enr.signature[:cls.private_key_size]


@pytest.fixture(autouse=True)
def mock_identity_scheme():
    assert MockIdentityScheme.id not in identity_scheme_registry
    identity_scheme_registry[MockIdentityScheme.id] = MockIdentityScheme

    yield MockIdentityScheme

    identity_scheme_registry.pop(MockIdentityScheme.id)


def test_mapping_interface():
    kv_pairs = {
        b"id": b"",
        b"key1": b"value1",
        b"key2": b"value2",
    }
    enr = ENR(signature=b"", sequence_number=0, kv_pairs=kv_pairs)

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


def test_inititialization():
    valid_sequence_number = 0
    valid_kv_pairs = {b"id": b""}
    valid_signature = b""  # signature is not validated during initialization

    assert UnsignedENR(
        sequence_number=valid_sequence_number,
        kv_pairs=valid_kv_pairs,
    )
    assert ENR(
        sequence_number=valid_sequence_number,
        kv_pairs=valid_kv_pairs,
        signature=valid_signature,
    )

    with pytest.raises(ValidationError):
        UnsignedENR(
            sequence_number=valid_sequence_number,
            kv_pairs={b"no-id": b""},
        )
    with pytest.raises(ValidationError):
        ENR(
            sequence_number=valid_sequence_number,
            kv_pairs={b"no-id": b""},
            signature=valid_signature,
        )

    with pytest.raises(ValidationError):
        UnsignedENR(
            sequence_number=-1,
            kv_pairs=valid_kv_pairs,
        )
    with pytest.raises(ValidationError):
        ENR(
            sequence_number=-1,
            kv_pairs=valid_kv_pairs,
            signature=valid_signature,
        )


def test_signing(mock_identity_scheme):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"})
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    assert enr.signature == mock_identity_scheme.create_signature(enr, private_key)


def test_signature_validation(mock_identity_scheme):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"})
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    enr.validate_signature()

    invalid_signature = b"\xff" * 64
    invalid_enr = ENR(enr.sequence_number, dict(enr), invalid_signature)
    with pytest.raises(ValidationError):
        invalid_enr.validate_signature()

    enr_with_unknown_id = ENR(0, {b"id": b"unknown"}, b"")
    with pytest.raises(ValidationError):
        enr_with_unknown_id.validate_signature()


def test_extract_node_address(mock_identity_scheme):
    unsigned_enr = UnsignedENR(0, {b"id": b"mock"})
    private_key = b"\x00" * 32
    enr = unsigned_enr.to_signed_enr(private_key)
    assert enr.extract_node_address() == private_key


def test_signature_scheme_selection(mock_identity_scheme):
    mock_enr = ENR(0, {b"id": b"mock"}, b"")
    assert mock_enr.get_identity_scheme() is mock_identity_scheme

    v4_enr = ENR(0, {b"id": b"v4"}, b"")
    assert v4_enr.get_identity_scheme() is V4IdentityScheme

    other_enr = ENR(0, {b"id": b"other"}, b"")
    with pytest.raises(ValidationError):
        other_enr.get_identity_scheme()


def test_repr(mock_identity_scheme):
    enr = UnsignedENR(0, {b"id": b"mock"}).to_signed_enr(b"\x00" * 32)
    base64_encoded_enr = base64.urlsafe_b64encode(rlp.encode(enr))
    represented_enr = repr(enr)

    assert represented_enr.startswith("enr:")
    assert base64_encoded_enr.rstrip(b"=").decode() == represented_enr[4:]

    assert ENR.from_repr(represented_enr) == enr


def test_deserialization_key_order_validation():
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
        rlp.decode(serialized_enr, ENRSedes)


def test_deserialization_key_uniqueness_validation():
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
        rlp.decode(serialized_enr, ENRSedes)


def test_deserialization_completeness_validation():
    incomplete_enrs = (
        rlp.encode([]),
        rlp.encode([
            b"signature",
        ]),
        rlp.encode([
            b"signature",
            0,
            b"key1",
        ]),
        rlp.encode([
            b"signature",
            0,
            b"key1",
            b"value1",
            b"id",
        ]),
    )
    for incomplete_enr in incomplete_enrs:
        with pytest.raises(rlp.DeserializationError):
            rlp.decode(incomplete_enr, ENRSedes)


def test_equality():
    base_kwargs = {
        "sequence_number": 0,
        "kv_pairs": {
            b"id": b"",
            b"key1": b"value1",
            b"key2": b"value2",
        },
        "signature": b"signature",
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


def test_serialization_roundtrip():
    original_enr = ENR(
        sequence_number=0,
        kv_pairs={
            b"id": b"",
            b"key2": b"value2",  # wrong order so that serialization is forced to fix this
            b"key1": b"value1",
        },
        signature=b"",
    )
    encoded = rlp.encode(original_enr)
    recovered_enr = rlp.decode(encoded, ENR)
    assert recovered_enr == original_enr


def test_official_test_vector():
    enr = ENR.from_repr(OFFICIAL_TEST_DATA["repr"])

    assert enr.sequence_number == OFFICIAL_TEST_DATA["sequence_number"]
    assert dict(enr) == OFFICIAL_TEST_DATA["kv_pairs"]
    assert enr.extract_node_address() == OFFICIAL_TEST_DATA["node_id"]
    assert enr.get_identity_scheme() is OFFICIAL_TEST_DATA["identity_scheme"]
    assert repr(enr) == OFFICIAL_TEST_DATA["repr"]

    unsigned_enr = UnsignedENR(enr.sequence_number, dict(enr))
    reconstructed_enr = unsigned_enr.to_signed_enr(OFFICIAL_TEST_DATA["private_key"])
    assert reconstructed_enr == enr
