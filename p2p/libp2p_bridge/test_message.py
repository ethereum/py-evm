import pytest

from p2p.libp2p_bridge.message import (
    Collation,
    CollationRequest,
    INT_BYTES,
)


def test_collation():
    with pytest.raises(ValueError):
        Collation.from_bytes(b"")
    with pytest.raises(ValueError):
        Collation.from_bytes(b"\x00" * (INT_BYTES * 2 - 1))
    Collation.from_bytes(b"\x00" * (INT_BYTES * 2))
    # test if `from_bytes` and `to_bytes` work well
    c1 = Collation(1, 2, b"\xbe\xef")
    c2 = Collation.from_bytes(c1.to_bytes())
    assert c1.shard_id == c2.shard_id
    assert c1.period == c2.period
    assert c1.blobs == c2.blobs


def test_message():
    with pytest.raises(ValueError):
        CollationRequest.from_bytes(b"")
    with pytest.raises(ValueError):
        CollationRequest.from_bytes(b"\x00" * (INT_BYTES * 2 - 1))
    CollationRequest.from_bytes(b"\x00" * (INT_BYTES * 2))
    # test if `from_bytes` and `to_bytes` work well
    cr1 = CollationRequest(1, 2, "beef")
    cr2 = CollationRequest.from_bytes(cr1.to_bytes())
    assert cr1.shard_id == cr2.shard_id
    assert cr1.period == cr2.period
    assert cr1.collation_hash == cr2.collation_hash
