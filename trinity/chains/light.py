from abc import ABCMeta, abstractmethod
from typing import Dict, Any

from eth_typing import (
    Address,
    Hash32,
)

from evm.rlp.headers import BlockHeader

from trinity.db.light import BaseLightDB


class BaseLightChain(metaclass=ABCMeta):
    lightdb: BaseLightDB = None
    header: BlockHeader = None

    def __init__(self, lightdb: BaseLightDB, header: BlockHeader) -> None:
        self.lightdb = lightdb
        self.header = header

    #
    # Chain Initialization API
    #
    @classmethod
    @abstractmethod
    def from_genesis(cls,
                     lightdb: BaseLightDB,
                     genesis_params: Dict[str, Any],
                     genesis_state: Dict[Address, Dict]) -> 'BaseLightChain':
        """
        Initializes the Chain from a genesis state.
        """
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            lightdb: BaseLightDB,
                            genesis_header: BlockHeader) -> 'BaseLightChain':
        """
        Initializes the chain from the genesis header.
        """
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the block header at the canonical chain head.

        Raises CanonicalHeadNotFound if there's no head defined for the canonical chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if there's no block header with the given hash in the db.
        """
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def import_header(self, header: BlockHeader) -> BlockHeader:
        """
        Import a new header to the chain.
        """
        raise NotImplementedError("Chain classes must implement this method")


class LightChain(BaseLightChain):
    @classmethod
    def from_genesis(cls,
                     lightdb: BaseLightDB,
                     genesis_params: Dict[str, Any],
                     genesis_state: Dict[Address, Dict]) -> 'BaseLightChain':
        """
        Initializes the Chain from a genesis state.
        """
        genesis_header = BlockHeader(**genesis_params)
        return cls.from_genesis_header(lightdb, genesis_header)

    @classmethod
    def from_genesis_header(cls,
                            lightdb: BaseLightDB,
                            genesis_header: BlockHeader) -> 'BaseLightChain':
        """
        Initializes the chain from the genesis header.
        """
        lightdb.persist_header(genesis_header)
        return cls(lightdb, genesis_header)
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Header API
    #
    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the block header at the canonical chain head.

        Raises CanonicalHeadNotFound if there's no head defined for the canonical chain.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if there's no block header with the given hash in the db.
        """
        raise NotImplementedError("Chain classes must implement this method")

    def import_header(self, header: BlockHeader) -> BlockHeader:
        """
        Import a new header to the chain.
        """
        raise NotImplementedError("Chain classes must implement this method")
