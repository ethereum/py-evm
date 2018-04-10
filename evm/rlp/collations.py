import rlp

from eth_utils import (
    encode_hex,
)

from evm.utils.datatypes import (
    Configurable,
)

from .headers import CollationHeader
from .sedes import collation_body


class Collation(rlp.Serializable, Configurable):

    fields = [
        ("header", CollationHeader),
        ("body", collation_body),
    ]

    @property
    def hash(self) -> bytes:
        return self.header.hash

    @property
    def shard_id(self) -> int:
        return self.header.shard_id

    @property
    def parent_hash(self) -> bytes:
        return self.header.parent_hash

    @property
    def chunk_root(self) -> bytes:
        return self.header.chunk_root

    @property
    def period(self) -> int:
        return self.header.period

    @property
    def height(self) -> int:
        return self.header.height

    @property
    def proposer_address(self) -> bytes:
        return self.header.proposer_address

    @property
    def proposer_bid(self) -> int:
        return self.header.proposer_bid

    @property
    def proposer_signature(self) -> bytes:
        return self.header.proposer_signature

    def __repr__(self) -> str:
        return "<Collation {} shard={} height={}>".format(
            self.__class__.__name__,
            encode_hex(self.hash)[2:10],
            self.shard_id,
            self.height,
        )

    def __str__(self) -> str:
        return "Collation {} shard={} height={} period={}".format(
            encode_hex(self.hash)[2:10],
            self.shard_id,
            self.height,
            self.period,
        )
