from p2p.logic import Application
from p2p.qualifiers import HasProtocol

from cached_property import cached_property

from .commands import (
    BroadcastData,
    GetSum,
    Sum,
)
from .payloads import (
    BroadcastDataPayload,
    GetSumPayload,
    SumPayload,
)
from .proto import ParagonProtocol


class ParagonAPI(Application):
    name = 'paragon'
    qualifier = HasProtocol(ParagonProtocol)

    @cached_property
    def protocol(self) -> ParagonProtocol:
        return self.connection.get_protocol_by_type(ParagonProtocol)

    def send_broadcast_data(self, data: bytes) -> None:
        self.protocol.send(BroadcastData(BroadcastDataPayload(data)))

    def send_get_sum(self, a: int, b: int) -> None:
        self.protocol.send(GetSum(GetSumPayload(a, b)))

    def send_sum(self, c: int) -> None:
        self.protocol.send(Sum(SumPayload(c)))
