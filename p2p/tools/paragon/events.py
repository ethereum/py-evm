from lahja import (
    BaseEvent,
)
from p2p.peer import (
    IdentifiablePeer,
)


class GetSumRequest(BaseEvent):

    def __init__(self, peer: IdentifiablePeer, a: int, b: int) -> None:
        self.peer = peer
        self.a = a
        self.b = b
