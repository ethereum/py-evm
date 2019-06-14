from dataclasses import (
    dataclass,
)
from typing import (
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)


@dataclass
class NetworkIdResponse(BaseEvent):

    network_id: int


class NetworkIdRequest(BaseRequestResponseEvent[NetworkIdResponse]):

    @staticmethod
    def expected_response_type() -> Type[NetworkIdResponse]:
        return NetworkIdResponse
