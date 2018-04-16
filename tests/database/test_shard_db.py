import pytest

from evm.db.shard import (
    ShardDB,
)
from evm.rlp.headers import (
    CollationHeader,
)
from evm.rlp.collations import (
    Collation,
)

from evm.utils.blobs import (
    calc_chunk_root,
)

from evm.db import (
    get_db_backend,
)

from evm.constants import (
    COLLATION_SIZE,
)
from evm.exceptions import (
    CanonicalCollationNotFound,
    CollationHeaderNotFound,
    CollationBodyNotFound,
)


@pytest.fixture
def shard_db():
    return ShardDB(get_db_backend())


@pytest.fixture
def body():
    return b"\xff" * COLLATION_SIZE


@pytest.fixture
def header(body):
    return CollationHeader(
        shard_id=0,
        chunk_root=calc_chunk_root(body),
        period=2,
        proposer_address=b"\x22" * 20
    )


@pytest.fixture
def collation(header, body):
    return Collation(header, body)


def test_header_lookup(shard_db, header):
    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_header_by_hash(header.hash)
    assert shard_db.availability_unknown(header.chunk_root)

    shard_db.add_header(header)
    assert header == shard_db.get_header_by_hash(header.hash)

    with pytest.raises(CollationBodyNotFound):
        shard_db.get_collation_by_hash(header.hash)

    assert shard_db.availability_unknown(header.chunk_root)


def test_body_lookup(shard_db, header, body):
    with pytest.raises(CollationBodyNotFound):
        shard_db.get_body_by_chunk_root(header.chunk_root)
    assert shard_db.availability_unknown(header.chunk_root)

    shard_db.add_body(body)
    assert body == shard_db.get_body_by_chunk_root(header.chunk_root)

    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_collation_by_hash(header.hash)

    assert shard_db.is_available(header.chunk_root)


def test_collation_lookup(shard_db, collation, header, body):
    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_header_by_hash(header.hash)
    with pytest.raises(CollationBodyNotFound):
        shard_db.get_body_by_chunk_root(header.chunk_root)
    assert shard_db.availability_unknown(header.chunk_root)

    shard_db.add_collation(collation)

    assert header == shard_db.get_header_by_hash(header.hash)
    assert body == shard_db.get_body_by_chunk_root(header.chunk_root)
    assert collation == shard_db.get_collation_by_hash(header.hash)

    assert shard_db.is_available(header.chunk_root)


def test_availabilities(shard_db, header):
    assert shard_db.availability_unknown(header.chunk_root)
    assert not shard_db.is_available(header.chunk_root)
    assert not shard_db.is_unavailable(header.chunk_root)

    shard_db.mark_unavailable(header.chunk_root)

    assert not shard_db.availability_unknown(header.chunk_root)
    assert not shard_db.is_available(header.chunk_root)
    assert shard_db.is_unavailable(header.chunk_root)

    shard_db.mark_available(header.chunk_root)

    assert not shard_db.availability_unknown(header.chunk_root)
    assert shard_db.is_available(header.chunk_root)
    assert not shard_db.is_unavailable(header.chunk_root)


def test_canonicality(shard_db, collation, header, body):
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_hash(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_header(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_body(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_collation(header.shard_id, header.period)

    shard_db.add_collation(collation)

    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_hash(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_header(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_body(header.shard_id, header.period)
    with pytest.raises(CanonicalCollationNotFound):
        shard_db.get_canonical_collation(header.shard_id, header.period)

    shard_db.mark_canonical(header)

    assert shard_db.get_canonical_hash(header.shard_id, header.period) == header.hash
    assert shard_db.get_canonical_header(header.shard_id, header.period) == header
    assert shard_db.get_canonical_body(header.shard_id, header.period) == body
    assert shard_db.get_canonical_collation(header.shard_id, header.period) == collation
