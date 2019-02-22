
from p2p.events import ConnectToNodeCommand

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.rpc.modules import BaseRPCModule
from trinity._utils.validation import validate_enode_uri


class Admin(BaseRPCModule):

    def __init__(self, event_bus: TrinityEventBusEndpoint) -> None:
        self.event_bus = event_bus

    @property
    def name(self) -> str:
        return 'admin'

    async def addPeer(self, node: str) -> None:
        validate_enode_uri(node, require_ip=True)

        self.event_bus.broadcast(
            ConnectToNodeCommand(node),
            TO_NETWORKING_BROADCAST_CONFIG
        )
