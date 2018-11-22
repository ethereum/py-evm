from abc import ABC, abstractmethod
from typing import Tuple

from eth_typing import BlockNumber, Hash32

from eth.chains.base import BaseChain
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt


# This class is a work in progress; its main purpose is to define the API of an asyncio-compatible
# Chain implementation.
class BaseAsyncChainAPI(ABC):
    @abstractmethod
    async def coro_import_block(self,
                                block: BlockHeader,
                                perform_validation: bool=True,
                                ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        pass

    @abstractmethod
    async def coro_validate_chain(
            self,
            parent: BlockHeader,
            chain: Tuple[BlockHeader, ...],
            seal_check_random_sample_rate: int = 1) -> None:
        pass

    @abstractmethod
    async def coro_validate_receipt(self,
                                    receipt: Receipt,
                                    at_header: BlockHeader) -> None:
        pass

    @abstractmethod
    async def coro_get_block_by_hash(self,
                                     block_hash: Hash32) -> BaseBlock:
        pass

    @abstractmethod
    async def coro_get_block_by_header(self,
                                       header: BlockHeader) -> BaseBlock:
        pass

    @abstractmethod
    async def coro_get_canonical_block_by_number(self,
                                                 block_number: BlockNumber) -> BaseBlock:
        pass


class BaseAsyncChain(BaseAsyncChainAPI, BaseChain):
    pass
