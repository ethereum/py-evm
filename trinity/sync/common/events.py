from typing import (
    Type,
    Union,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from trinity.sync.common.types import (
    SyncProgress
)


class SyncingResponse(BaseEvent):

    def __init__(self, syncing: Union[bool, SyncProgress]) -> None:
        self.syncing = syncing


class SyncingRequest(BaseRequestResponseEvent[SyncingResponse]):

    @staticmethod
    def expected_response_type() -> Type[SyncingResponse]:
        return SyncingResponse
