import rlp
from rlp.sedes import (
    big_endian_int,
)

from evm.rlp.headers import (
    CollationHeader,
)
from evm.rlp.collations import (
    Collation,
)

from evm.exceptions import (
    CollationBodyNotFound,
    CollationHeaderNotFound,
)


def make_collation_header_lookup_key(shard_id: int, period: int) -> bytes:
    return b"collation-header-lookup:shard_id=%d,period=%d" % (shard_id, period)


def make_collation_body_lookup_key(shard_id: int, period: int) -> bytes:
    return b"collation-body-lookup:shard_id=%d,period=%d" % (shard_id, period)


def make_collation_availability_lookup_key(shard_id: int, period: int) -> bytes:
    return b"collation-availability-lookup:shard_id=%d,period=%d" % (shard_id, period)


class ShardDB:
    """Stores collation headers and bodies, as well as flags for unavailable bodies."""

    def __init__(self, db):
        self.db = db

    #
    # Collation and header API
    #
    def get_header(self, shard_id: int, period: int) -> CollationHeader:
        key = make_collation_header_lookup_key(shard_id, period)
        try:
            header = self.db.get(key)
        except KeyError:
            raise CollationHeaderNotFound("No header for shard {} and period {} found".format(
                shard_id,
                period,
            ))
        return rlp.decode(header, sedes=CollationHeader)

    def get_body(self, shard_id: int, period: int) -> bytes:
        key = make_collation_body_lookup_key(shard_id, period)
        try:
            body = self.db.get(key)
        except KeyError:
            raise CollationBodyNotFound("No body for shard {} and period {} found".format(
                shard_id,
                period,
            ))
        return body

    def get_collation(self, shard_id: int, period: int) -> Collation:
        header = self.get_header(shard_id, period)
        body = self.get_body(shard_id, period)
        return Collation(header, body)

    def add_header(self, header: CollationHeader) -> None:
        key = make_collation_header_lookup_key(header.shard_id, header.period)
        self.db.set(key, rlp.encode(header))

    def add_body(self, shard_id: int, period: int, body: bytes) -> None:
        key = make_collation_body_lookup_key(shard_id, period)
        self.db.set(key, body)
        self.mark_available(shard_id, period)

    def add_collation(self, collation: Collation) -> None:
        self.add_header(collation.header)
        self.add_body(collation.shard_id, collation.period, collation.body)

    #
    # Availability API
    #
    def mark_unavailable(self, shard_id: int, period: int) -> None:
        key = make_collation_availability_lookup_key(shard_id, period)
        self.db.set(key, rlp.encode(False))

    def mark_available(self, shard_id: int, period: int) -> None:
        key = make_collation_availability_lookup_key(shard_id, period)
        self.db.set(key, rlp.encode(True))

    def is_available(self, shard_id: int, period: int) -> bool:
        key = make_collation_availability_lookup_key(shard_id, period)
        try:
            available = bool(rlp.decode(self.db.get(key), big_endian_int))
        except KeyError:
            return False
        return available

    def is_unavailable(self, shard_id: int, period: int) -> bool:
        key = make_collation_availability_lookup_key(shard_id, period)
        try:
            available = bool(rlp.decode(self.db.get(key), big_endian_int))
        except KeyError:
            return False
        return not available

    def availability_unknown(self, shard_id: int, period: int) -> bool:
        key = make_collation_availability_lookup_key(shard_id, period)
        return not self.db.exists(key)
