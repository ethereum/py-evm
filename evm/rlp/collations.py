import rlp

from evm.utils.datatypes import (
    Configurable,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from .headers import CollationHeader
from .sedes import collation_body

from eth_typing import (
    Address,
    Hash32,
)


class Collation(rlp.Serializable, Configurable):

    fields = [
        ("header", CollationHeader),
        ("body", collation_body),
    ]

    @property
    def hash(self) -> Hash32:
        return self.header.hash

    @property
    def shard_id(self) -> int:
        return self.header.shard_id

    @property
    def chunk_root(self) -> Hash32:
        return self.header.chunk_root

    @property
    def period(self) -> int:
        return self.header.period

    @property
    def proposer_address(self) -> Address:
        return self.header.proposer_address

    def __repr__(self) -> str:
        return "<Collation shard={} period={} hash={}>".format(
            self.shard_id,
            self.period,
            encode_hex(self.hash)[2:10],
        )
