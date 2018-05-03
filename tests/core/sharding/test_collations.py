import pytest

from evm.rlp.headers import (
    CollationHeader,
)
from evm.rlp.collations import (
    Collation,
)


@pytest.fixture
def collation_header():
    return CollationHeader(
        shard_id=0,
        chunk_root=b"\x11" * 32,
        period=2,
        proposer_address=b"\x22" * 20
    )


def test_smc_encoding_decoding(collation_header):
    encoded = collation_header.encode_for_smc()
    assert len(encoded) == CollationHeader.smc_encoded_size
    assert encoded == b"".join([
        b"\x00" * 32,
        b"\x11" * 32,
        b"\x00" * 31 + b"\x02",
        b"\x00" * 12 + b"\x22" * 20
    ])

    decoded = CollationHeader.decode_from_smc(encoded)
    assert decoded == collation_header


def test_body_fields(collation_header):
    assert len(CollationHeader._meta.fields) == 4  # if not this test is outdated
    collation = Collation(header=collation_header, body=b"")

    assert collation.hash == collation_header.hash
    assert collation.shard_id == collation_header.shard_id
    assert collation.chunk_root == collation_header.chunk_root
    assert collation.period == collation_header.period
    assert collation.proposer_address == collation_header.proposer_address
