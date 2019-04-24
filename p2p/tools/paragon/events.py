from lahja import (
    BaseEvent,
)
from p2p.kademlia import Node


class GetSumRequest(BaseEvent):

    def __init__(self, remote: Node, a: int, b: int) -> None:
        self.remote = remote
        self.a = a
        self.b = b
