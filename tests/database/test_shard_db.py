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


from evm.db import (
    get_db_backend,
)

from evm.constants import (
    COLLATION_SIZE,
)
from evm.exceptions import (
    CollationHeaderNotFound,
    CollationBodyNotFound,
)


@pytest.fixture
def shard_db():
    return ShardDB(get_db_backend())


@pytest.fixture
def header():
    return CollationHeader(
        shard_id=0,
        chunk_root=b"\x11" * 32,
        period=2,
        proposer_address=b"\x22" * 20
    )


@pytest.fixture
def body():
    return b"\xff" * COLLATION_SIZE


@pytest.fixture
def collation(header, body):
    return Collation(header, body)


def test_header_lookup(shard_db, header):
    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_header(header.shard_id, header.period)
    assert shard_db.availability_unknown(header.shard_id, header.period)

    shard_db.add_header(header)
    assert header == shard_db.get_header(header.shard_id, header.period)

    with pytest.raises(CollationBodyNotFound):
        shard_db.get_collation(header.shard_id, header.period)

    assert shard_db.availability_unknown(header.shard_id, header.period)


def test_body_lookup(shard_db, header, body):
    with pytest.raises(CollationBodyNotFound):
        shard_db.get_body(header.shard_id, header.period)
    assert shard_db.availability_unknown(header.shard_id, header.period)

    shard_db.add_body(header.shard_id, header.period, body)
    assert body == shard_db.get_body(header.shard_id, header.period)

    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_collation(header.shard_id, header.period)

    assert shard_db.is_available(header.shard_id, header.period)


def test_collation_lookup(shard_db, collation, header, body):
    with pytest.raises(CollationHeaderNotFound):
        shard_db.get_header(header.shard_id, header.period)
    with pytest.raises(CollationBodyNotFound):
        shard_db.get_body(header.shard_id, header.period)
    assert shard_db.availability_unknown(header.shard_id, header.period)

    shard_db.add_collation(collation)

    assert header == shard_db.get_header(header.shard_id, header.period)
    assert body == shard_db.get_body(header.shard_id, header.period)
    assert collation == shard_db.get_collation(header.shard_id, header.period)

    assert shard_db.is_available(header.shard_id, header.period)


def test_availabilities(shard_db, header):
    assert shard_db.availability_unknown(header.shard_id, header.period)
    assert not shard_db.is_available(header.shard_id, header.period)
    assert not shard_db.is_unavailable(header.shard_id, header.period)

    shard_db.mark_unavailable(header.shard_id, header.period)

    assert not shard_db.availability_unknown(header.shard_id, header.period)
    assert not shard_db.is_available(header.shard_id, header.period)
    assert shard_db.is_unavailable(header.shard_id, header.period)

    shard_db.mark_available(header.shard_id, header.period)

    assert not shard_db.availability_unknown(header.shard_id, header.period)
    assert shard_db.is_available(header.shard_id, header.period)
    assert not shard_db.is_unavailable(header.shard_id, header.period)
