from p2p.kademlia import Node
from p2p.validation import validate_enode_uri

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.protocol.common.events import ConnectToNodeCommand
from trinity.rpc.modules import BaseRPCModule


class Admin(BaseRPCModule):

    def __init__(self, event_bus: TrinityEventBusEndpoint) -> None:
        self.event_bus = event_bus

    async def addPeer(self, uri: str) -> None:
        validate_enode_uri(uri, require_ip=True)

        await self.event_bus.broadcast(
            ConnectToNodeCommand(Node.from_uri(uri)),
            TO_NETWORKING_BROADCAST_CONFIG
        )
