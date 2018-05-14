from typing import (
    Union,
)
from eth_typing import (
    Hash32,
)

from evm.db.shard import (
    Availability,
    ShardDB,
)

from evm.exceptions import (
    ValidationError,
)

from evm.rlp.headers import (
    CollationHeader,
)
from evm.rlp.collations import (
    Collation,
)


class Shard:

    def __init__(self, shard_db: ShardDB, shard_id: int) -> None:
        self.shard_id = shard_id
        self.shard_db = shard_db

    #
    # Header/Collation Retrieval
    #
    def get_header_by_hash(self, collation_hash: Hash32) -> CollationHeader:
        return self.shard_db.get_header_by_hash(collation_hash)

    def get_collation_by_hash(self, collation_hash: Hash32) -> Collation:
        return self.shard_db.get_collation_by_hash(collation_hash)

    def get_header_by_period(self, period: int) -> CollationHeader:
        return self.shard_db.get_canonical_header(self.shard_id, period)

    def get_collation_by_period(self, period: int) -> CollationHeader:
        return self.shard_db.get_canonical_collation(self.shard_id, period)

    def get_availability(self, header: CollationHeader) -> Availability:
        return self.shard_db.get_availability(header.chunk_root)

    #
    # Header/Collation Insertion
    #
    def add_header(self, header: CollationHeader) -> None:
        check_shard_id(self, header)
        self.shard_db.add_header(header)

    def add_collation(self, collation: Collation) -> None:
        check_shard_id(self, collation)
        self.shard_db.add_collation(collation)

    def set_unavailable(self, header: CollationHeader) -> None:
        check_shard_id(self, header)
        self.shard_db.set_availability(header.chunk_root, Availability.UNAVAILABLE)

    def set_canonical(self, header: CollationHeader) -> None:
        check_shard_id(self, header)
        self.shard_db.set_canonical(header)


def check_shard_id(shard: Shard, header_or_collation: Union[CollationHeader, Collation]) -> None:
    if header_or_collation.shard_id != shard.shard_id:
        raise ValidationError(
            "Header or collation belongs to shard {} instead of shard {}".format(
                header_or_collation.shard_id,
                shard.shard_id,
            )
        )
