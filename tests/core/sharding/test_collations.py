import pytest

from eth_keys import keys

from evm.utils.padding import (
    pad32,
)

from evm.rlp.headers import (
    CollationHeader,
    UnsignedCollationHeader,
)


@pytest.fixture
def proposer_key():
    return keys.PrivateKey(pad32(b"proposer"))


@pytest.fixture
def proposer_address(proposer_key):
    return proposer_key.public_key.to_canonical_address()


@pytest.fixture
def unsigned_collation_header(proposer_address):
    return UnsignedCollationHeader(
        shard_id=0,
        parent_hash=b"\x11" * 32,
        chunk_root=b"\x22" * 32,
        period=3,
        height=4,
        proposer_address=proposer_address,
        proposer_bid=5,
    )


@pytest.fixture
def collation_header(unsigned_collation_header, proposer_key):
    return unsigned_collation_header.to_signed_collation_header(proposer_key)


def test_signing(unsigned_collation_header, proposer_key):
    wrong_private_key = keys.PrivateKey(pad32(b"no proposer"))
    with pytest.raises(ValueError):
        unsigned_collation_header.to_signed_collation_header(wrong_private_key)
    collation_header = unsigned_collation_header.to_signed_collation_header(proposer_key)

    assert (
        UnsignedCollationHeader.serialize(collation_header) ==
        UnsignedCollationHeader.serialize(unsigned_collation_header)
    )
    assert len(collation_header.proposer_signature) == 96


def test_is_genesis(collation_header):
    assert collation_header.height != 0
    assert not collation_header.is_genesis

    genesis_collation_header = CollationHeader(
        shard_id=0,
        parent_hash=b"\x11" * 32,
        chunk_root=b"\x22" * 32,
        period=3,
        height=0,
        proposer_address=proposer_address,
        proposer_bid=5,
        proposer_signature=b"\x66" * 32,
    )
    assert genesis_collation_header.is_genesis


def test_smc_encoding_decoding(collation_header):
    encoded = collation_header.encode_for_smc()
    decoded = CollationHeader.decode_from_smc(encoded)
    assert decoded == collation_header


def test_child_generation(collation_header):
    child = UnsignedCollationHeader.from_parent(
        collation_header,
        chunk_root=b"\xff" * 32,
        period=100,
        proposer_address=b"\xee" * 32,
        proposer_bid=99,
    )
    assert child.shard_id == collation_header.shard_id
    assert child.height == collation_header.height + 1
    assert child.parent_hash == collation_header.hash
