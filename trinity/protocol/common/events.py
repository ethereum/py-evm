from p2p.peer import PeerMessage

from trinity.extensibility.events import BaseEvent


class NewChainTipEvent(BaseEvent):
    """
    Broadcasted when a new tip (in regular or light protocol) is received from a peer.
    """
    def __init__(self, peer_message: PeerMessage) -> None:
        self.peer_message = peer_message
