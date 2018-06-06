# Tell mypy to ignore this import as a workaround for https://github.com/python/mypy/issues/4049
from trinity.rpc.modules import (  # type: ignore
    RPCModule,
)


class Net(RPCModule):
    def version(self):
        """
        Returns the current network ID.
        """
        return str(self._chain.network_id)

    def peerCount(self):
        """
        Return the number of peers that are currently connected to the node
        """
        if self._p2p_server.peer_pool is None:
            return '0x0'

        return hex(len(self._p2p_server.peer_pool))

    def listening(self):
        """
        Return `True` if the client is actively listening for network connections
        """
        if self._p2p_server.peer_pool is None:
            return False

        return True
