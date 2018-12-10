from p2p.events import PeerCountRequest
from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.nodes.events import NetworkIdRequest
from trinity.rpc.modules import RPCModule


class Net(RPCModule):
    async def version(self) -> str:
        """
        Returns the current network ID.
        """
        response = await self._event_bus.request(
            NetworkIdRequest(),
            TO_NETWORKING_BROADCAST_CONFIG
        )
        return str(response.network_id)

    async def peerCount(self) -> str:
        """
        Return the number of peers that are currently connected to the node
        """
        response = await self._event_bus.request(
            PeerCountRequest(),
            TO_NETWORKING_BROADCAST_CONFIG
        )
        return hex(response.peer_count)

    async def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        return True
