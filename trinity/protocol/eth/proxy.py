from typing import (
    Sequence,
    Tuple,
)

from eth.abc import (
    BlockAPI,
    BlockHeaderAPI,
    ReceiptAPI,
    SignedTransactionAPI,
)
from eth_typing import (
    BlockIdentifier,
    Hash32,
)
from eth_utils import get_extended_debug_logger
from lahja import (
    BroadcastConfig,
    EndpointAPI,
)

from p2p.abc import SessionAPI

from trinity._utils.errors import SupportsError
from trinity.protocol.common.typing import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)
from trinity.rlp.block_body import BlockBody

from .commands import (
    BlockBodies,
    BlockHeaders,
    NodeData,
    Receipts,
    Transactions,
)
from .events import (
    GetBlockBodiesRequest,
    GetBlockHeadersRequest,
    GetNodeDataRequest,
    GetReceiptsRequest,
    SendBlockBodiesEvent,
    SendBlockHeadersEvent,
    SendNodeDataEvent,
    SendReceiptsEvent,
    SendTransactionsEvent,
)


class ProxyETHAPI:
    """
    An ``ETHAPI`` that can be used outside of the process that runs the peer pool. Any
    action performed on this class is delegated to the process that runs the peer pool.
    """
    logger = get_extended_debug_logger('trinity.protocol.eth.proxy.ProxyETHAPI')

    def __init__(self,
                 session: SessionAPI,
                 event_bus: EndpointAPI,
                 broadcast_config: BroadcastConfig):
        self.session = session
        self._event_bus = event_bus
        self._broadcast_config = broadcast_config

    def raise_if_needed(self, value: SupportsError) -> None:
        if value.error is not None:
            self.logger.warning(
                "Raised %s while fetching from peer %s", value.error, self.session,
            )
            raise value.error

    async def get_block_headers(self,
                                block_number_or_hash: BlockIdentifier,
                                max_headers: int = None,
                                skip: int = 0,
                                reverse: bool = True,
                                timeout: float = None) -> Tuple[BlockHeaderAPI, ...]:

        response = await self._event_bus.request(
            GetBlockHeadersRequest(
                self.session,
                block_number_or_hash,
                max_headers,
                skip,
                reverse,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s block headers from %s",
            len(response.headers),
            self.session
        )

        return tuple(response.headers)

    async def get_block_bodies(self,
                               headers: Sequence[BlockHeaderAPI],
                               timeout: float = None) -> BlockBodyBundles:

        response = await self._event_bus.request(
            GetBlockBodiesRequest(
                self.session,
                headers,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s block bodies from %s",
            len(response.bundles),
            self.session
        )

        return response.bundles

    async def get_node_data(self,
                            node_hashes: Sequence[Hash32],
                            timeout: float = None) -> NodeDataBundles:

        response = await self._event_bus.request(
            GetNodeDataRequest(
                self.session,
                node_hashes,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s node bundles from %s",
            len(response.bundles),
            self.session
        )

        return response.bundles

    async def get_receipts(self,
                           headers: Sequence[BlockHeaderAPI],
                           timeout: float = None) -> ReceiptsBundles:

        response = await self._event_bus.request(
            GetReceiptsRequest(
                self.session,
                headers,
                timeout,
            ),
            self._broadcast_config
        )

        self.raise_if_needed(response)

        self.logger.debug2(
            "ProxyETHExchangeHandler returning %s receipt bundles from %s",
            len(response.bundles),
            self.session
        )

        return response.bundles

    def send_transactions(self,
                          txns: Sequence[SignedTransactionAPI]) -> None:
        command = Transactions(tuple(txns))
        self._event_bus.broadcast_nowait(
            SendTransactionsEvent(self.session, command),
            self._broadcast_config,
        )

    def send_block_headers(self, headers: Sequence[BlockHeaderAPI]) -> None:
        command = BlockHeaders(tuple(headers))
        self._event_bus.broadcast_nowait(
            SendBlockHeadersEvent(self.session, command),
            self._broadcast_config,
        )

    def send_block_bodies(self, blocks: Sequence[BlockAPI]) -> None:
        block_bodies = tuple(
            BlockBody(block.transactions, block.uncles)
            for block in blocks
        )
        command = BlockBodies(block_bodies)
        self._event_bus.broadcast_nowait(
            SendBlockBodiesEvent(self.session, command),
            self._broadcast_config,
        )

    def send_receipts(self, receipts: Sequence[Sequence[ReceiptAPI]]) -> None:
        command = Receipts(tuple(map(tuple, receipts)))
        self._event_bus.broadcast_nowait(
            SendReceiptsEvent(self.session, command),
            self._broadcast_config,
        )

    def send_node_data(self, nodes: Sequence[bytes]) -> None:
        command = NodeData(tuple(nodes))
        self._event_bus.broadcast_nowait(
            SendNodeDataEvent(self.session, command),
            self._broadcast_config,
        )
