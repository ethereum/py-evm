from typing import (
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)


class NetworkIdResponse(BaseEvent):

    def __init__(self, network_id: int) -> None:
        self.network_id = network_id


class NetworkIdRequest(BaseRequestResponseEvent[NetworkIdResponse]):

    @staticmethod
    def expected_response_type() -> Type[NetworkIdResponse]:
        return NetworkIdResponse
