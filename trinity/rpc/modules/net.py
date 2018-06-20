from trinity.rpc.modules import (
    RPCModule,
)


class Net(RPCModule):
    def version(self) -> str:
        """
        Returns the current network ID.
        """
        return str(self._chain.network_id)

    def peerCount(self) -> str:
        """
        Return the number of peers that are currently connected to the node
        """
        return hex(len(self._peer_pool))  # type: ignore

    def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        return True
