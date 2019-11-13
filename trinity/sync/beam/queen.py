from abc import ABC, abstractmethod

from p2p.abc import AsyncioServiceAPI
from p2p.exchange import PerformanceAPI

from trinity.protocol.eth.commands import (
    NodeData,
)
from trinity.protocol.eth.peer import ETHPeer
from trinity.sync.beam.constants import (
    NON_IDEAL_RESPONSE_PENALTY,
)
from trinity.sync.common.peers import WaitingPeers


def queen_peer_performance_sort(tracker: PerformanceAPI) -> float:
    return -1 * tracker.items_per_second_ema.value


def _peer_sort_key(peer: ETHPeer) -> float:
    return queen_peer_performance_sort(peer.eth_api.get_node_data.tracker)


class QueenTrackerAPI(ABC):
    """
    Keep track of the single best peer
    """
    @abstractmethod
    async def get_queen_peer(self) -> ETHPeer:
        ...

    @abstractmethod
    def penalize_queen(self, peer: ETHPeer) -> None:
        ...


class QueenTrackerMixin(QueenTrackerAPI, AsyncioServiceAPI):
    # The best peer gets skipped for backfill, because we prefer to use it for
    #   urgent beam sync nodes
    _queen_peer: ETHPeer = None
    _waiting_peers: WaitingPeers[ETHPeer]

    def __init__(self) -> None:
        self._waiting_peers = WaitingPeers(NodeData)

    def _update_queen(self, peer: ETHPeer) -> ETHPeer:
        '''
        @return peer that is no longer queen
        '''
        if self._queen_peer is None:
            self._queen_peer = peer
            return None
        elif peer == self._queen_peer:
            # nothing to do, peer is already the queen
            return None
        elif _peer_sort_key(peer) < _peer_sort_key(self._queen_peer):
            old_queen, self._queen_peer = self._queen_peer, peer
            self._waiting_peers.put_nowait(old_queen)
            return old_queen
        else:
            # nothing to do, peer is slower than the queen
            return None

    async def get_queen_peer(self) -> ETHPeer:
        while self._queen_peer is None:
            peer = await self._waiting_peers.get_fastest()
            self._update_queen(peer)

        return self._queen_peer

    def penalize_queen(self, peer: ETHPeer) -> None:
        if peer == self._queen_peer:
            self._queen_peer = None

            delay = NON_IDEAL_RESPONSE_PENALTY
            self.logger.debug(
                "Penalizing %s for %.2fs, for minor infraction",
                peer,
                delay,
            )
            self.call_later(delay, self._waiting_peers.put_nowait, peer)
