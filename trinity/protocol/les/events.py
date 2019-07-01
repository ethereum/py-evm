from dataclasses import (
    dataclass,
)
from typing import (
    Tuple,
)

from eth.rlp.headers import BlockHeader
from lahja import BaseEvent
from p2p.kademlia import Node

from trinity.protocol.common.events import (
    PeerPoolMessageEvent,
)


class GetBlockHeadersEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockHeaders`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


@dataclass
class SendBlockHeadersEvent(BaseEvent):
    """
    Event to proxy a ``LESPeer.sub_proto.send_block_heades`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    remote: Node
    headers: Tuple[BlockHeader, ...]
    buffer_value: int
    request_id: int
