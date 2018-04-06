from rlp.sedes import (
    Binary,
)

from evm.rlp.headers import CollationHeader
from evm.rlp.collations import BaseCollation

from evm.constants import (
    COLLATION_SIZE,
)


class Collation(BaseCollation):
    fields = [
        ('header', CollationHeader),
        ('body', Binary.fixed_length(COLLATION_SIZE)),
    ]

    #
    # Helpers
    #
    @property
    def hash(self):
        return self.header.hash

    @property
    def shard_id(self):
        return self.header.shard_id

    @property
    def parent_hash(self):
        return self.header.parent_hash

    @property
    def chunk_root(self):
        return self.header.chunk_root

    @property
    def period(self):
        return self.header.period

    @property
    def number(self):
        return self.header.number

    @property
    def proposer_address(self):
        return self.header.proposer_address

    @property
    def proposer_bid(self):
        return self.header.proposer_bid

    @property
    def proposer_signature(self):
        return self.header.proposer_signature

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the collation denoted by the given collation header.
        """
        body = chaindb.get_collation_body(header.chunk_root)
        return cls(
            header=header,
            body=body,
        )
