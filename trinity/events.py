from lahja import (
    BaseEvent
)


class PeerCountRequest(BaseEvent):

    def __init__(self) -> None:
        super().__init__(None)

class PeerCountResponse(BaseEvent):
    pass