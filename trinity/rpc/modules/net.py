from p2p.events import (
    PeerCountRequest
)
from trinity.rpc.modules import (
    RPCModule,
)


class Net(RPCModule):
    async def version(self) -> str:
        """
        Returns the current network ID.
        """
        return str(self._chain.network_id)

    async def peerCount(self) -> str:
        """
        Return the number of peers that are currently connected to the node
        """
        response = await self._event_bus.request(PeerCountRequest())
        return hex(response.peer_count)

    async def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        return True
