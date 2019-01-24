from typing import (
    Tuple,
)

from eth.rlp.headers import BlockHeader
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


class SendBlockHeadersEvent(HasRemoteEvent):
    """
    Event to proxy a ``LESPeer.sub_proto.send_block_heades`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    def __init__(self,
                 remote: Node,
                 headers: Tuple[BlockHeader, ...],
                 buffer_value: int,
                 request_id: int=None) -> None:
        self._remote = remote
        self.headers = headers
        self.buffer_value = buffer_value
        self.request_id = request_id

    @property
    def remote(self) -> Node:
        return self._remote
