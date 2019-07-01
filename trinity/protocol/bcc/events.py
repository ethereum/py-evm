from dataclasses import (
    dataclass,
)
from typing import (
    Tuple,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from lahja import (
    BaseEvent,
)

from p2p.kademlia import (
    Node,
)

from trinity.protocol.common.events import (
    PeerPoolMessageEvent,
)


class GetBeaconBlocksEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBeaconBlocks`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


@dataclass
class SendBeaconBlocksEvent(BaseEvent):
    """
    Event to proxy a ``BccPeer.sub_proto.send_blocks`` call from a proxy peer to the actual peer
    that sits in the peer pool.
    """
    remote: Node
    blocks: Tuple[BaseBeaconBlock, ...]
    request_id: int
