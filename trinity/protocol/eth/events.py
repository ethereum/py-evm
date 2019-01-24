from typing import (
    List,
    Tuple,
)

from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from p2p.kademlia import (
    Node,
)

from trinity.protocol.common.events import (
    HasRemoteEvent,
    PeerPoolMessageEvent,
)


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


class SendBlockHeadersEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_headers`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    def __init__(self, remote: Node, headers: Tuple[BlockHeader, ...]) -> None:
        self._remote = remote
        self.headers = headers

    @property
    def remote(self) -> Node:
        return self._remote


class SendBlockBodiesEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_block_bodies`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    def __init__(self, remote: Node, blocks: List[BaseBlock]) -> None:
        self._remote = remote
        self.blocks = blocks

    @property
    def remote(self) -> Node:
        return self._remote


class SendNodeDataEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_node_data`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    def __init__(self, remote: Node, nodes: Tuple[bytes, ...]) -> None:
        self._remote = remote
        self.nodes = nodes

    @property
    def remote(self) -> Node:
        return self._remote


class SendReceiptsEvent(HasRemoteEvent):
    """
    Event to proxy a ``ETHPeer.sub_proto.send_receipts`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    def __init__(self, remote: Node, receipts: List[List[Receipt]]) -> None:
        self._remote = remote
        self.receipts = receipts

    @property
    def remote(self) -> Node:
        return self._remote
