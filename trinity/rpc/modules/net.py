from p2p.events import PeerCountRequest
from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.nodes.events import NetworkIdRequest
from trinity.rpc.modules import BaseRPCModule


class Net(BaseRPCModule):

    def __init__(self, event_bus: TrinityEventBusEndpoint):
        self.event_bus = event_bus

    @property
    def name(self) -> str:
        return 'net'

    async def version(self) -> str:
        """
        Returns the current network ID.
        """
        response = await self.event_bus.request(
            NetworkIdRequest(),
            TO_NETWORKING_BROADCAST_CONFIG
        )
        return str(response.network_id)

    async def peerCount(self) -> str:
        """
        Return the number of peers that are currently connected to the node
        """
        response = await self.event_bus.request(
            PeerCountRequest(),
            TO_NETWORKING_BROADCAST_CONFIG
        )
        return hex(response.peer_count)

    async def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        return True
