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
        # We don't have a common type that exposes a peer_pool field
        # inject PeerPool directly when the following issue is solved
        # https://github.com/ethereum/py-evm/pull/934
        if self._p2p_server.peer_pool is None:  # type: ignore
            return '0x0'

        return hex(len(self._p2p_server.peer_pool))  # type: ignore

    def listening(self) -> bool:
        """
        Return `True` if the client is actively listening for network connections
        """
        # We don't have a common type that exposes a peer_pool field
        # inject PeerPool directly when the following issue is solved
        # https://github.com/ethereum/py-evm/pull/934
        if self._p2p_server.peer_pool is None:  # type: ignore
            return False

        return True
