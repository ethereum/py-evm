from abc import (
    ABCMeta,
    abstractmethod,
)

from eth_typing import Hash32, Address

from evm.rlp.blocks import BaseBlock
from evm.chain.base import BaseChain


class BaseRPCDB(metaclass=ABCMeta):
    """
    The minimal necessary API to fulfill JSON-RPC requests.
    """
    @abstractmethod
    def get_pending_block(self) -> BaseBlock:
        """
        Return the unmined *pending* block from chain.
        """
        pass

    @abstractmethod
    def get_canonical_head_block(self) -> BaseBlock:
        """
        Return the block from the canonical chain HEAD.
        """
        pass

    @abstractmethod
    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        """
        Return the block with the given hash.  Raises `BlockNotFound` if the
        block is not known.
        """
        pass

    @abstractmethod
    def get_block_by_number(self, block_number: int) -> BaseBlock:
        """
        Return the block with the given number.  Raises `BlockNotFound` if the
        block is not known.
        """
        pass

    @abstractmethod
    def get_account(self, address: Address, at_block: Hash32=None):
        """
        Return the account object for the given account at the given block.  If
        `at_block` is `None` then the current latest canonical head will be
        used.
        """
        pass


class DirectRPCDB(BaseRPCDB):
    chain: BaseChain = None

    def __init__(self, chain: BaseChain):
        self.chain = chain

    def get_pending_block(self) -> BaseBlock:
        return self.chain.get_vm().block

    def get_canonical_head_block(self) -> BaseBlock:
        return self.chain.get_canonical_head()

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        return self.chain.get_block_by_hash(self, block_hash)

    def get_block_by_number(self, block_number: int) -> BaseBlock:
        return self.chain.get_canonical_block_by_number(self, block_number)

    def get_account(self, address: Address, at_block: Hash32=None):
        # TODO
        raise NotImplementedError('Not implemented')
