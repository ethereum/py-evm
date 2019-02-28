import asyncio
import inspect
from typing import (  # noqa: F401
    Any,
    Optional,
    Callable,
    Coroutine,
    cast,
    Dict,
    Generator,
    Iterator,
    Tuple,
    Type,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)

from eth.chains.base import (
    AccountState,
)
from eth.db.backends.base import BaseDB
from eth.db.chain import (
    BaseChainDB,
)
from eth.db.header import (
    BaseHeaderDB,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.headers import (
    BlockHeader,
    HeaderParams,
)
from eth.rlp.receipts import (
    Receipt
)
from eth.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from eth.typing import (
    BaseOrSpoofTransaction,
)
from eth.vm.computation import (
    BaseComputation
)

from trinity.sync.light.service import (
    BaseLightPeerChain,
)
from trinity._utils.async_dispatch import (
    async_method,
)

from .base import BaseAsyncChain

if TYPE_CHECKING:
    from eth.vm.base import BaseVM  # noqa: F401


class LightDispatchChain(BaseAsyncChain):
    """
    Provide the :class:`BaseChain` API, even though only a
    :class:`BaseLightPeerChain` is syncing. Store results locally so that not
    all requests hit the light peer network.
    """

    ASYNC_TIMEOUT_SECONDS = 10
    _loop = None

    def __init__(self, headerdb: BaseHeaderDB, peer_chain: BaseLightPeerChain) -> None:
        self._headerdb = headerdb
        self._peer_chain = peer_chain
        self._peer_chain_loop = asyncio.get_event_loop()

    #
    # Helpers
    #
    @classmethod
    def get_chaindb_class(cls) -> Type[BaseChainDB]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Chain API
    #
    @classmethod
    def from_genesis(cls,
                     base_db: BaseDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseAsyncChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    @classmethod
    def from_genesis_header(cls,
                            base_db: BaseDB,
                            genesis_header: BlockHeader) -> 'BaseAsyncChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_chain_at_block_parent(self, block: BaseBlock) -> 'BaseAsyncChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # VM API
    #
    def get_vm(self, header: BlockHeader=None) -> 'BaseVM':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Header API
    #
    def create_header_from_parent(self,
                                  parent_header: BlockHeader,
                                  **header_params: HeaderParams) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        return self._headerdb.get_block_header_by_hash(block_hash)

    def get_canonical_head(self) -> BlockHeader:
        return self._headerdb.get_canonical_head()

    def get_score(self, block_hash: Hash32) -> int:
        return self._headerdb.get_score(block_hash)

    #
    # Block API
    #
    def get_ancestors(self, limit: int, header: BlockHeader) -> Tuple[BaseBlock, ...]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block(self) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        raise NotImplementedError("Use coro_get_block_by_hash")

    async def coro_get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        header = self._headerdb.get_block_header_by_hash(block_hash)
        return await self.coro_get_block_by_header(header)

    def get_block_by_header(self, header: BlockHeader) -> BaseBlock:
        raise NotImplementedError("Use coro_get_block_by_header")

    async def coro_get_block_by_header(self, header: BlockHeader) -> BaseBlock:
        # TODO check local cache, before hitting peer

        block_body = await self._peer_chain.coro_get_block_body_by_hash(header.hash)

        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        transactions = [
            block_class.transaction_class.from_base_transaction(tx)
            for tx in block_body.transactions
        ]
        return block_class(
            header=header,
            transactions=transactions,
            uncles=block_body.uncles,
        )

    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        raise NotImplementedError("Use coro_get_canonical_block_by_number")

    async def coro_get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        """
        Return the block with the given number from the canonical chain.
        Raises HeaderNotFound if it is not found.
        """
        header = self._headerdb.get_canonical_block_header_by_number(block_number)
        return await self.get_block_by_header(header)

    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        return self._headerdb.get_canonical_block_hash(block_number)

    def build_block_with_transactions(self,
                                      transactions: Tuple[BaseTransaction, ...],
                                      parent_header: BlockHeader=None) -> Tuple[BaseBlock, Tuple[Receipt, ...], Tuple[BaseComputation, ...]]:        # noqa: E501
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Transaction API
    #
    def create_transaction(self, *args: Any, **kwargs: Any) -> BaseTransaction:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> BaseUnsignedTransaction:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_canonical_transaction(self, transaction_hash: Hash32) -> BaseTransaction:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_transaction_receipt(self, transaction_hash: Hash32) -> Receipt:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Execution API
    #
    def apply_transaction(
            self,
            transaction: BaseTransaction) -> Tuple[BaseBlock, Receipt, BaseComputation]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_transaction_result(
            self,
            transaction: BaseOrSpoofTransaction,
            at_header: BlockHeader) -> bytes:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def estimate_gas(
            self,
            transaction: BaseOrSpoofTransaction,
            at_header: BlockHeader=None) -> int:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def import_block(self, block: BaseBlock, perform_validation: bool=True) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    async def coro_import_block(self, block: BaseBlock, perform_validation: bool=True) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def mine_block(self, *args: Any, **kwargs: Any) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Validation API
    #
    def validate_receipt(self, receipt: Receipt, at_header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    async def coro_validate_receipt(self, receipt: Receipt, at_header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_block(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_gaslimit(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_seal(self, header: BlockHeader) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_uncles(self, block: BaseBlock) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    coro_validate_chain = async_method('validate_chain')
