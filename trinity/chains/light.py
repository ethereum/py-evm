import asyncio
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
    BlockNumber,
    Hash32,
)

from evm.chains.base import (
    Chain,
)
from evm.db.header import (
    BaseHeaderDB,
)
from evm.rlp.blocks import (
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
)

from p2p.lightchain import (
    LightPeerChain,
)

if TYPE_CHECKING:
    from evm.vm.base import BaseVM  # noqa: F401


class LightDispatchChain(Chain):
    """
    Provide the :class:`BaseChain` API, even though only a
    :class:`LightPeerChain` is syncing. Store results locally so that not
    all requests hit the light peer network.
    """

    ASYNC_TIMEOUT_SECONDS = 10
    _loop = None

    def __init__(self, headerdb: BaseHeaderDB, peer_chain: LightPeerChain) -> None:
        self._headerdb = headerdb
        self._peer_chain = peer_chain
        self._peer_chain_loop = asyncio.get_event_loop()

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        return self._headerdb.get_block_header_by_hash(block_hash)

    def get_canonical_head(self) -> BlockHeader:
        return self._headerdb.get_canonical_head()

    def get_score(self, block_hash: Hash32) -> int:
        return self._headerdb.get_score(block_hash)

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        header = self._headerdb.get_block_header_by_hash(block_hash)
        return self.get_block_by_header(header)

    def get_block_by_header(self, header: BlockHeader) -> BaseBlock:
        # TODO check local cache, before hitting peer
        block_body = self._run_async(
            self._peer_chain.get_block_body_by_hash(header.hash)
        )

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
        """
        Return the block with the given number from the canonical chain.
        Raises HeaderNotFound if it is not found.
        """
        header = self._headerdb.get_canonical_block_header_by_number(block_number)
        return self.get_block_by_header(header)

    def get_canonical_block_hash(self, block_number: int) -> Hash32:
        return self._headerdb.get_canonical_block_hash(block_number)

    #
    # Async utils
    #
    T = TypeVar('T')

    def _run_async(self, async_method: Coroutine[T, Any, Any]) -> T:
        future = asyncio.run_coroutine_threadsafe(async_method, loop=self._peer_chain_loop)
        return future.result(self.ASYNC_TIMEOUT_SECONDS)
