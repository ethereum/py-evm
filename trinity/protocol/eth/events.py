from dataclasses import (
    dataclass,
)
from typing import (
    List,
    Tuple,
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from lahja import (
    BaseEvent,
)
from p2p.kademlia import (
    Node,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from trinity.protocol.common.events import (
    HasRemoteEvent,
    HasRemoteAndTimeoutRequest,
    PeerPoolMessageEvent,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)


# Events flowing from PeerPool to Proxy

class GetBlockHeadersEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockHeaders`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class GetBlockBodiesEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockBodies`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class GetReceiptsEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetReceipts`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class GetNodeDataEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetNodeData`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class TransactionsEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``Transactions`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class NewBlockHashesEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``Transactions`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass

# Events flowing from Proxy to PeerPool


@dataclass
class SendBlockHeadersEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_headers`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """

    headers: Tuple[BlockHeader, ...]


@dataclass
class SendBlockBodiesEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_bodies`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    blocks: List[BaseBlock]


@dataclass
class SendNodeDataEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_node_data`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    nodes: Tuple[bytes, ...]


@dataclass
class SendReceiptsEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_receipts`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    receipts: List[List[Receipt]]


# EXCHANGE HANDLER REQUEST / RESPONSE PAIRS

@dataclass
class GetBlockHeadersResponse(BaseEvent):

    headers: Tuple[BlockHeader, ...]
    exception: Exception = None  # noqa: E701


@dataclass
class GetBlockHeadersRequest(HasRemoteAndTimeoutRequest[GetBlockHeadersResponse]):

    remote: Node
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
    exception: Exception = None  # noqa: E701


@dataclass
class GetBlockBodiesRequest(HasRemoteAndTimeoutRequest[GetBlockBodiesResponse]):

    remote: Node
    headers: Tuple[BlockHeader, ...]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetBlockBodiesResponse]:
        return GetBlockBodiesResponse


@dataclass
class GetNodeDataResponse(BaseEvent):

    bundles: NodeDataBundles
    exception: Exception = None  # noqa: E701


@dataclass
class GetNodeDataRequest(HasRemoteAndTimeoutRequest[GetNodeDataResponse]):

    remote: Node
    node_hashes: Tuple[Hash32, ...]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetNodeDataResponse]:
        return GetNodeDataResponse


@dataclass
class GetReceiptsResponse(BaseEvent):

    bundles: ReceiptsBundles
    exception: Exception = None  # noqa: E701


@dataclass
class GetReceiptsRequest(HasRemoteAndTimeoutRequest[GetReceiptsResponse]):

    remote: Node
    headers: Tuple[BlockHeader, ...]
    timeout: float

    @staticmethod
    def expected_response_type() -> Type[GetReceiptsResponse]:
        return GetReceiptsResponse
