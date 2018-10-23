from typing import (
    Optional,
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from trinity.sync.common.types import (
    SyncProgress
)


class SyncingResponse(BaseEvent):
    def __init__(self, is_syncing: bool, progress: Optional[SyncProgress]) -> None:
        self.is_syncing: bool = is_syncing
        self.progress: Optional[SyncProgress] = progress


class SyncingRequest(BaseRequestResponseEvent[SyncingResponse]):
    @staticmethod
    def expected_response_type() -> Type[SyncingResponse]:
        return SyncingResponse
