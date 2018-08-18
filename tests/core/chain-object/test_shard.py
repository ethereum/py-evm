import pytest

import random
import itertools

from eth_utils import (
    int_to_big_endian,
)

from eth.chains.shard import (
    Shard,
)
from eth.db.shard import (
    ShardDB,
    Availability,
)
from eth.db import (
    get_db_backend,
)

from eth.rlp.headers import (
    CollationHeader,
)
from eth.rlp.collations import (
    Collation,
)

from eth.constants import (
    COLLATION_SIZE,
)

from eth.utils.blobs import (
    calc_chunk_root,
)
from eth.utils.padding import (
    zpad_right,
)


@pytest.fixture
def shard_db():
    return ShardDB(get_db_backend())


@pytest.fixture
def shard(shard_db):
    return Shard(shard_db, shard_id=0)


def random_collation(shard_id, period):
    body = zpad_right(int_to_big_endian(random.getrandbits(8 * 32)), COLLATION_SIZE)
    header = CollationHeader(
        shard_id=shard_id,
        period=period,
        chunk_root=calc_chunk_root(body),
        proposer_address=b"\xff" * 20,
    )
    return Collation(header, body)


def test_insertion(shard):
    collations = [random_collation(0, period) for period in range(3)]

    shard.add_header(collations[0].header)
    assert shard.get_header_by_hash(collations[0].hash) == collations[0].header
    assert shard.get_availability(collations[0].header) is Availability.UNKNOWN

    shard.add_collation(collations[1])
    assert shard.get_collation_by_hash(collations[1].hash) == collations[1]
    assert shard.get_availability(collations[1].header) is Availability.AVAILABLE

    shard.add_header(collations[2].header)
    shard.set_unavailable(collations[2].header)
    assert shard.get_header_by_hash(collations[2].hash) == collations[2].header
    assert shard.get_availability(collations[2].header) is Availability.UNAVAILABLE


def test_retrieval(shard):
    branch1 = [random_collation(0, period) for period in range(3)]
    branch2 = [random_collation(0, period) for period in range(3)]
    for collation in itertools.chain(branch1, branch2):
        shard.add_collation(collation)
    for collation in branch1:
        shard.set_canonical(collation)

    for collation in itertools.chain(branch1, branch2):
        shard.get_header_by_hash(collation.hash) == collation.header
        shard.get_collation_by_hash(collation.hash) == collation

    for collation in branch1:
        shard.get_header_by_period(collation.period) == collation.header
        shard.get_collation_by_period(collation.period) == collation
