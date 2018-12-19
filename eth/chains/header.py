from abc import ABC, abstractmethod
from typing import (      # noqa: F401
    Any,
    cast,
    Dict,
    Tuple,
    Type,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth.db.backends.base import (
    BaseAtomicDB,
    BaseDB,
)
from eth.db.header import (  # noqa: F401
    BaseHeaderDB,
    HeaderDB,
)
from eth.rlp.headers import BlockHeader
from eth._utils.datatypes import (
    Configurable,
)
from eth.vm.base import BaseVM  # noqa: F401


class BaseHeaderChain(Configurable, ABC):
    _base_db = None  # type: BaseDB

    _headerdb_class = None  # type: Type[BaseHeaderDB]
    _headerdb = None  # type: BaseHeaderDB

    header = None  # type: BlockHeader
    chain_id = None  # type: int
    vm_configuration = None  # type: Tuple[Tuple[int, Type[BaseVM]], ...]

    @abstractmethod
    def __init__(self, base_db: BaseDB, header: BlockHeader=None) -> None:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Chain Initialization API
    #
    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            base_db: BaseDB,
                            genesis_header: BlockHeader) -> 'BaseHeaderChain':
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Helpers
    #
    @classmethod
    @abstractmethod
    def get_headerdb_class(cls) -> Type[BaseHeaderDB]:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Canonical Chain API
    #
    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def import_header(self,
                      header: BlockHeader
                      ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        raise NotImplementedError("Chain classes must implement this method")


class HeaderChain(BaseHeaderChain):
    _headerdb_class = HeaderDB  # type: Type[BaseHeaderDB]

    def __init__(self, base_db: BaseDB, header: BlockHeader=None) -> None:
        self.base_db = base_db
        self.headerdb = self.get_headerdb_class()(cast(BaseAtomicDB, base_db))

        if header is None:
            self.header = self.get_canonical_head()
        else:
            self.header = header

    #
    # Chain Initialization API
    #
    @classmethod
    def from_genesis_header(cls,
                            base_db: BaseDB,
                            genesis_header: BlockHeader) -> 'BaseHeaderChain':
        """
        Initializes the chain from the genesis header.
        """
        headerdb = cls.get_headerdb_class()(cast(BaseAtomicDB, base_db))
        headerdb.persist_header(genesis_header)
        return cls(base_db, genesis_header)

    #
    # Helpers
    #
    @classmethod
    def get_headerdb_class(cls) -> Type[BaseHeaderDB]:
        """
        Returns the class which should be used for the `headerdb`
        """
        if cls._headerdb_class is None:
            raise AttributeError("HeaderChain classes must set a `headerdb_class`")
        return cls._headerdb_class

    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        """
        Direct passthrough to `headerdb`
        """
        return self.headerdb.get_canonical_block_hash(block_number)

    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        """
        Direct passthrough to `headerdb`
        """
        return self.headerdb.get_canonical_block_header_by_number(block_number)

    def get_canonical_head(self) -> BlockHeader:
        """
        Direct passthrough to `headerdb`
        """
        return self.headerdb.get_canonical_head()

    #
    # Header API
    #
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Direct passthrough to `headerdb`
        """
        return self.headerdb.get_block_header_by_hash(block_hash)

    def header_exists(self, block_hash: Hash32) -> bool:
        """
        Direct passthrough to `headerdb`
        """
        return self.headerdb.header_exists(block_hash)

    def import_header(self,
                      header: BlockHeader
                      ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        """
        Direct passthrough to `headerdb`

        Also updates the local `header` property to be the latest canonical head.

        Returns an iterable of headers representing the headers that are newly
        part of the canonical chain.

        - If the imported header is not part of the canonical chain then an
          empty tuple will be returned.
        - If the imported header simply extends the canonical chain then a
          length-1 tuple with the imported header will be returned.
        - If the header is part of a non-canonical chain which overtakes the
          current canonical chain then the returned tuple will contain the
          headers which are newly part of the canonical chain.
        """
        new_canonical_headers = self.headerdb.persist_header(header)
        self.header = self.get_canonical_head()
        return new_canonical_headers
