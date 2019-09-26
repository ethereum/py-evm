from dataclasses import (
    dataclass,
)
from typing import (
    Sequence,
    Type,
)

from eth.abc import (
    BlockHeaderAPI,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from p2p.abc import SessionAPI

from trinity.protocol.common.events import (
    PeerPoolMessageEvent,
)
from trinity.protocol.common.typing import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)

from .commands import (
    BlockBodies,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetNodeData,
    GetReceipts,
    NewBlock,
    NewBlockHashes,
    NodeData,
    Receipts,
    Transactions,
)


# Events flowing from PeerPool to Proxy

class GetBlockHeadersEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockHeaders`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: GetBlockHeaders


class GetBlockBodiesEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockBodies`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: GetBlockBodies


class GetReceiptsEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetReceipts`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: GetReceipts


class GetNodeDataEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetNodeData`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: GetNodeData


class TransactionsEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``Transactions`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: Transactions


class NewBlockEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``NewBlock`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: NewBlock


class NewBlockHashesEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``Transactions`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    command: NewBlockHashes

# Events flowing from Proxy to PeerPool


@dataclass
class SendBlockHeadersEvent(BaseEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_headers`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    session: SessionAPI
    command: BlockHeaders


@dataclass
class SendBlockBodiesEvent(BaseEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_bodies`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    session: SessionAPI
    command: BlockBodies


@dataclass
class SendNodeDataEvent(BaseEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_node_data`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    session: SessionAPI
    command: NodeData


@dataclass
class SendReceiptsEvent(BaseEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_receipts`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    session: SessionAPI
    command: Receipts


@dataclass
class SendTransactionsEvent(BaseEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_transactions`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    session: SessionAPI
    command: Transactions

# EXCHANGE HANDLER REQUEST / RESPONSE PAIRS


@dataclass
class GetBlockHeadersResponse(BaseEvent):

    headers: Sequence[BlockHeaderAPI]
    error: Exception = None


@dataclass
class GetBlockHeadersRequest(BaseRequestResponseEvent[GetBlockHeadersResponse]):

    session: SessionAPI
    block_number_or_hash: BlockIdentifier
    max_headers: int
    skip: int
    reverse: bool
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetBlockHeadersResponse]:
        return GetBlockHeadersResponse


@dataclass
class GetBlockBodiesResponse(BaseEvent):

    bundles: BlockBodyBundles
    error: Exception = None


@dataclass
class GetBlockBodiesRequest(BaseRequestResponseEvent[GetBlockBodiesResponse]):

    session: SessionAPI
    headers: Sequence[BlockHeaderAPI]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetBlockBodiesResponse]:
        return GetBlockBodiesResponse


@dataclass
class GetNodeDataResponse(BaseEvent):

    bundles: NodeDataBundles
    error: Exception = None


@dataclass
class GetNodeDataRequest(BaseRequestResponseEvent[GetNodeDataResponse]):

    session: SessionAPI
    node_hashes: Sequence[Hash32]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetNodeDataResponse]:
        return GetNodeDataResponse


@dataclass
class GetReceiptsResponse(BaseEvent):

    bundles: ReceiptsBundles
    error: Exception = None


@dataclass
class GetReceiptsRequest(BaseRequestResponseEvent[GetReceiptsResponse]):

    session: SessionAPI
    headers: Sequence[BlockHeaderAPI]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetReceiptsResponse]:
        return GetReceiptsResponse
