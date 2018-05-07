from enum import Enum

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

from evm.utils.blobs import (
    calc_chunk_root,
)

from evm.exceptions import (
    CanonicalCollationNotFound,
    CollationBodyNotFound,
    CollationHeaderNotFound,
)

from eth_typing import (
    Hash32,
)


class Availability(Enum):
    AVAILABLE = 0
    UNAVAILABLE = 1
    UNKNOWN = 2


def make_collation_availability_lookup_key(chunk_root: Hash32) -> bytes:
    return b"collation-availability-lookup:%s" % chunk_root


def make_canonical_hash_lookup_key(shard_id: int, period: int) -> bytes:
    return b"canonical-hash-lookup:shard_id=%d,period=%d" % (shard_id, period)


class ShardDB:
    """Stores collation headers and bodies, as well as flags for unavailable bodies."""

    def __init__(self, db):
        self.db = db

    #
    # Collation Getters by Hash
    #
    def get_header_by_hash(self, collation_hash: Hash32) -> CollationHeader:
        try:
            header = self.db[collation_hash]
        except KeyError:
            raise CollationHeaderNotFound("No header with hash {} found".format(collation_hash))
        return rlp.decode(header, sedes=CollationHeader)

    def get_body_by_chunk_root(self, chunk_root: Hash32) -> bytes:
        try:
            body = self.db[chunk_root]
        except KeyError:
            raise CollationBodyNotFound("No body with chunk root {} found".format(chunk_root))
        return body

    def get_collation_by_hash(self, collation_hash: Hash32) -> Collation:
        header = self.get_header_by_hash(collation_hash)
        body = self.get_body_by_chunk_root(header.chunk_root)
        return Collation(header, body)

    #
    # Canonical Collations
    #
    def set_canonical(self, header: CollationHeader) -> None:
        try:
            self.get_header_by_hash(header.hash)
        except CollationHeaderNotFound:
            raise ValueError("Cannot set unknown header as canonical: {}".format(
                header.hash
            ))
        key = make_canonical_hash_lookup_key(header.shard_id, header.period)
        self.db.set(key, header.hash)

    def get_canonical_collation_hash(self, shard_id: int, period: int) -> Hash32:
        key = make_canonical_hash_lookup_key(shard_id, period)
        try:
            canonical_hash = self.db[key]
        except KeyError:
            raise CanonicalCollationNotFound(
                "No collation set as canonical for shard {} and period {}".format(
                    shard_id,
                    period,
                )
            )
        else:
            return canonical_hash

    def get_canonical_header(self, shard_id: int, period: int) -> CollationHeader:
        collation_hash = self.get_canonical_collation_hash(shard_id, period)
        return self.get_header_by_hash(collation_hash)

    def get_canonical_body(self, shard_id: int, period: int) -> bytes:
        header = self.get_canonical_header(shard_id, period)
        return self.get_body_by_chunk_root(header.chunk_root)

    def get_canonical_collation(self, shard_id: int, period: int) -> Collation:
        collation_hash = self.get_canonical_collation_hash(shard_id, period)
        return self.get_collation_by_hash(collation_hash)

    #
    # Collation Setters
    #
    def add_header(self, header: CollationHeader) -> None:
        self.db.set(header.hash, rlp.encode(header))

    def add_body(self, body: bytes) -> None:
        chunk_root = calc_chunk_root(body)
        self.db.set(chunk_root, body)
        self.set_availability(chunk_root, Availability.AVAILABLE)

    def add_collation(self, collation: Collation) -> None:
        self.add_header(collation.header)
        self.add_body(collation.body)

    #
    # Availability API
    #
    def set_availability(self, chunk_root: Hash32, availability: Availability) -> None:
        key = make_collation_availability_lookup_key(chunk_root)
        if availability is Availability.AVAILABLE:
            self.db.set(key, rlp.encode(1))
        elif availability is Availability.UNAVAILABLE:
            self.db.set(key, rlp.encode(0))
        elif availability is Availability.UNKNOWN:
            if self.db.exists(key):
                self.db.delete(key)

    def get_availability(self, chunk_root: Hash32) -> Availability:
        key = make_collation_availability_lookup_key(chunk_root)
        try:
            availability_entry = self.db[key]
        except KeyError:
            return Availability.UNKNOWN
        else:
            available = bool(rlp.decode(availability_entry, big_endian_int))
            if available:
                return Availability.AVAILABLE
            else:
                return Availability.UNAVAILABLE
