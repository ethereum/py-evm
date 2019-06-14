import logging
from typing import (
    cast,
    Tuple,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.logging import (
    ExtendedDebugLogger,
)
from eth_typing import (
    BlockIdentifier,
    Hash32,
)
from lahja import (
    AsyncioEndpoint,
    BroadcastConfig,
)
from p2p.kademlia import (
    Node,
)

from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)

from .events import (
    GetBlockBodiesRequest,
    GetBlockHeadersRequest,
    GetNodeDataRequest,
    GetReceiptsRequest,
)
from .exchanges import (
    GetBlockBodiesExchange,
    GetBlockHeadersExchange,
    GetNodeDataExchange,
    GetReceiptsExchange,
)


class ETHExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_bodies': GetBlockBodiesExchange,
        'get_block_headers': GetBlockHeadersExchange,
        'get_node_data': GetNodeDataExchange,
        'get_receipts': GetReceiptsExchange,
    }

    # These are needed only to please mypy.
    get_block_bodies: GetBlockBodiesExchange
    get_node_data: GetNodeDataExchange
    get_receipts: GetReceiptsExchange


class ProxyETHExchangeHandler:
    """
    An ``ETHExchangeHandler`` that can be used outside of the process that runs the peer pool. Any
    action performed on this class is delegated to the process that runs the peer pool.
    """

    def __init__(self,
                 remote: Node,
                 event_bus: AsyncioEndpoint,
                 broadcast_config: BroadcastConfig):
        self.remote = remote
        self._event_bus = event_bus
        self._broadcast_config = broadcast_config
        self.logger = cast(
            ExtendedDebugLogger,
            logging.getLogger('trinity.protocol.eth.handlers.ProxyETHExchangeHandler')
        )

    def raise_if_needed(self, exception: Exception) -> None:
        if exception is not None:
            self.logger.warning(
                "Raised %s while fetching from peer %s", exception, self.remote.uri
            )
            raise exception

    async def get_block_headers(self,
                                block_number_or_hash: BlockIdentifier,
                                max_headers: int = None,
                                skip: int = 0,
                                reverse: bool = True,
                                timeout: float = None) -> Tuple[BlockHeader, ...]:

        response = await self._event_bus.request(
            GetBlockHeadersRequest(
                self.remote,
                block_number_or_hash,
                max_headers,
                skip,
                reverse,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response.exception)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s block headers from %s",
            len(response.headers),
            self.remote
        )

        return response.headers

    async def get_block_bodies(self,
                               headers: Tuple[BlockHeader, ...],
                               timeout: float = None) -> BlockBodyBundles:

        response = await self._event_bus.request(
            GetBlockBodiesRequest(
                self.remote,
                headers,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response.exception)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s block bodies from %s",
            len(response.bundles),
            self.remote
        )

        return response.bundles

    async def get_node_data(self,
                            node_hashes: Tuple[Hash32, ...],
                            timeout: float = None) -> NodeDataBundles:

        response = await self._event_bus.request(
            GetNodeDataRequest(
                self.remote,
                node_hashes,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response.exception)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s node bundles from %s",
            len(response.bundles),
            self.remote
        )

        return response.bundles

    async def get_receipts(self,
                           headers: Tuple[BlockHeader, ...],
                           timeout: float = None) -> ReceiptsBundles:

        response = await self._event_bus.request(
            GetReceiptsRequest(
                self.remote,
                headers,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response.exception)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s receipt bundles from %s",
            len(response.bundles),
            self.remote
        )

        return response.bundles
