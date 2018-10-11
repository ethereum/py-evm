from lahja import (
    BaseEvent
)


class ShutdownRequest(BaseEvent):

    def __init__(self, reason: str="") -> None:
        self.reason = reason
