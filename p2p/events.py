from lahja import (
    BaseEvent
)


class PeerCountRequest(BaseEvent):
    pass


class PeerCountResponse(BaseEvent):

    def __init__(self, peer_count: int) -> None:
        self.peer_count = peer_count
