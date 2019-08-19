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

from eth.abc import (
    BlockAPI,
    BlockHeaderAPI,
    ChainDatabaseAPI,
    ComputationAPI,
    DatabaseAPI,
    HeaderDatabaseAPI,
    ReceiptAPI,
    SignedTransactionAPI,
    UnsignedTransactionAPI,
    VirtualMachineAPI,
)
from eth.chains.base import (
    AccountState,
    Chain,
)
from eth.rlp.headers import (
    HeaderParams,
)

from trinity._utils.async_dispatch import async_method
from trinity.db.eth1.chain import AsyncChainDB
from trinity.sync.light.service import BaseLightPeerChain

from .base import AsyncChainAPI


class LightDispatchChain(AsyncChainAPI, Chain):
    """
    Provide the :class:`ChainAPI` API, even though only a
    :class:`BaseLightPeerChain` is syncing. Store results locally so that not
    all requests hit the light peer network.
    """
    chaindb_class = AsyncChainDB

    ASYNC_TIMEOUT_SECONDS = 10
    _loop = None

    def __init__(self, headerdb: HeaderDatabaseAPI, peer_chain: BaseLightPeerChain) -> None:
        self._headerdb = headerdb
        self._peer_chain = peer_chain
        self._peer_chain_loop = asyncio.get_event_loop()

    #
    # Helpers
    #
    @classmethod
    def get_chaindb_class(cls) -> Type[ChainDatabaseAPI]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Chain API
    #
    @classmethod
    def from_genesis(cls,
                     base_db: DatabaseAPI,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'LightDispatchChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    @classmethod
    def from_genesis_header(cls,
                            base_db: DatabaseAPI,
                            genesis_header: BlockHeaderAPI) -> 'LightDispatchChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_chain_at_block_parent(self, block: BlockAPI) -> 'LightDispatchChain':
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # VM API
    #
    def get_vm(self, header: BlockHeaderAPI=None) -> VirtualMachineAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Header API
    #
    def create_header_from_parent(self,
                                  parent_header: BlockHeaderAPI,
                                  **header_params: HeaderParams) -> BlockHeaderAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        return self._headerdb.get_block_header_by_hash(block_hash)

    coro_get_block_header_by_hash = async_method(Chain.get_block_header_by_hash)

    def get_canonical_head(self) -> BlockHeaderAPI:
        return self._headerdb.get_canonical_head()

    coro_get_canonical_head = async_method(Chain.get_canonical_head)

    def get_score(self, block_hash: Hash32) -> int:
        return self._headerdb.get_score(block_hash)

    #
    # Block API
    #
    def get_ancestors(self, limit: int, header: BlockHeaderAPI) -> Tuple[BlockAPI, ...]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    async def coro_get_ancestors(self, limit: int, header: BlockHeaderAPI) -> Tuple[BlockAPI, ...]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block(self) -> BlockAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_block_by_hash(self, block_hash: Hash32) -> BlockAPI:
        raise NotImplementedError("Use coro_get_block_by_hash")

    async def coro_get_block_by_hash(self, block_hash: Hash32) -> BlockAPI:
        header = self._headerdb.get_block_header_by_hash(block_hash)
        return await self.coro_get_block_by_header(header)

    def get_block_by_header(self, header: BlockHeaderAPI) -> BlockAPI:
        raise NotImplementedError("Use coro_get_block_by_header")

    async def coro_get_block_by_header(self, header: BlockHeaderAPI) -> BlockAPI:
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

    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BlockAPI:
        raise NotImplementedError("Use coro_get_canonical_block_by_number")

    async def coro_get_canonical_block_by_number(self, block_number: BlockNumber) -> BlockAPI:
        """
        Return the block with the given number from the canonical chain.
        Raises HeaderNotFound if it is not found.
        """
        header = self._headerdb.get_canonical_block_header_by_number(block_number)
        return await self.get_block_by_header(header)

    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        return self._headerdb.get_canonical_block_hash(block_number)

    def build_block_with_transactions(self,
                                      transactions: Tuple[SignedTransactionAPI, ...],
                                      parent_header: BlockHeaderAPI=None) -> Tuple[BlockAPI, Tuple[ReceiptAPI, ...], Tuple[ComputationAPI, ...]]:        # noqa: E501
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Transaction API
    #
    def create_transaction(self, *args: Any, **kwargs: Any) -> SignedTransactionAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> UnsignedTransactionAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_canonical_transaction(self, transaction_hash: Hash32) -> SignedTransactionAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_transaction_receipt(self, transaction_hash: Hash32) -> ReceiptAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Execution API
    #
    def apply_transaction(
            self,
            transaction: SignedTransactionAPI) -> Tuple[BlockAPI, ReceiptAPI, ComputationAPI]:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def get_transaction_result(
            self,
            transaction: SignedTransactionAPI,
            at_header: BlockHeaderAPI) -> bytes:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def estimate_gas(
            self,
            transaction: SignedTransactionAPI,
            at_header: BlockHeaderAPI=None) -> int:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def import_block(self, block: BlockAPI, perform_validation: bool=True) -> BlockAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    async def coro_import_block(self, block: BlockAPI, perform_validation: bool=True) -> BlockAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def mine_block(self, *args: Any, **kwargs: Any) -> BlockAPI:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    #
    # Validation API
    #
    def validate_receipt(self, receipt: ReceiptAPI, at_header: BlockHeaderAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    async def coro_validate_receipt(self, receipt: ReceiptAPI, at_header: BlockHeaderAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_block(self, block: BlockAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_gaslimit(self, header: BlockHeaderAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_seal(self, header: BlockHeaderAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    def validate_uncles(self, block: BlockAPI) -> None:
        raise NotImplementedError("Chain classes must implement " + inspect.stack()[0][3])

    coro_validate_chain = async_method(Chain.validate_chain)
