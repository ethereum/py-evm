from typing import (
    Tuple,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)

from p2p.kademlia import (
    Node,
)

from trinity.protocol.common.events import (
    HasRemoteEvent,
    PeerPoolMessageEvent,
)


class GetBeaconBlocksEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBeaconBlocks`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


class SendBeaconBlocksEvent(HasRemoteEvent):
    """
    Event to proxy a ``BccPeer.sub_proto.send_blocks`` call from a proxy peer to the actual peer
    that sits in the peer pool.
    """
    def __init__(self,
                 remote: Node,
                 blocks: Tuple[BaseBeaconBlock, ...],
                 request_id: int) -> None:
        self._remote = remote
        self.blocks = blocks
        self.request_id = request_id

    @property
    def remote(self) -> Node:
        return self._remote
