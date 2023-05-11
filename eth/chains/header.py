from typing import (
    Tuple,
    Type,
    cast,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
    HeaderChainAPI,
    HeaderDatabaseAPI,
)
from eth.db.backends.base import (
    BaseAtomicDB,
)
from eth.db.header import (
    HeaderDB,
)


class HeaderChain(Configurable, HeaderChainAPI):
    _base_db: AtomicDatabaseAPI = None
    _headerdb: HeaderDatabaseAPI = None

    _headerdb_class: Type[HeaderDatabaseAPI] = HeaderDB

    def __init__(
        self, base_db: AtomicDatabaseAPI, header: BlockHeaderAPI = None
    ) -> None:
        self.base_db = base_db
        self.headerdb = self.get_headerdb_class()(base_db)

        if header is None:
            self.header = self.get_canonical_head()
        else:
            self.header = header

    #
    # Chain Initialization API
    #
    @classmethod
    def from_genesis_header(
        cls, base_db: AtomicDatabaseAPI, genesis_header: BlockHeaderAPI
    ) -> HeaderChainAPI:
        headerdb = cls.get_headerdb_class()(cast(BaseAtomicDB, base_db))
        headerdb.persist_header(genesis_header)
        return cls(base_db, genesis_header)

    #
    # Helpers
    #
    @classmethod
    def get_headerdb_class(cls) -> Type[HeaderDatabaseAPI]:
        if cls._headerdb_class is None:
            raise AttributeError("HeaderChain classes must set a `headerdb_class`")
        return cls._headerdb_class

    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        return self.headerdb.get_canonical_block_hash(block_number)

    def get_canonical_block_header_by_number(
        self, block_number: BlockNumber
    ) -> BlockHeaderAPI:
        return self.headerdb.get_canonical_block_header_by_number(block_number)

    def get_canonical_head(self) -> BlockHeaderAPI:
        return self.headerdb.get_canonical_head()

    #
    # Header API
    #
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        return self.headerdb.get_block_header_by_hash(block_hash)

    def header_exists(self, block_hash: Hash32) -> bool:
        return self.headerdb.header_exists(block_hash)

    def import_header(
        self, header: BlockHeaderAPI
    ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        new_canonical_headers = self.headerdb.persist_header(header)
        self.header = self.get_canonical_head()
        return new_canonical_headers
