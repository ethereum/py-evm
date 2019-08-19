from asyncio import (
    PriorityQueue,
)
from typing import (
    Callable,
    Generic,
    Type,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)

from p2p.protocol import Command

from trinity.protocol.common.peer import BaseChainPeer
from trinity.protocol.common.trackers import (
    BasePerformance,
)
from trinity._utils.datastructures import (
    SortableTask,
)

TChainPeer = TypeVar('TChainPeer', bound=BaseChainPeer)


def _items_per_second(tracker: BasePerformance) -> float:
    """
    Sort so that highest items per second have the lowest value.
    They should be sorted first, so they are popped off the queue first.
    """
    return -1 * tracker.items_per_second_ema.value


class WaitingPeers(Generic[TChainPeer]):
    """
    Peers waiting to perform some action. When getting a peer from this queue,
    prefer the peer with the best throughput for the given command.
    """
    _waiting_peers: 'PriorityQueue[SortableTask[TChainPeer]]'

    def __init__(
            self,
            response_command_type: Type[Command],
            sort_key: Callable[[BasePerformance], float]=_items_per_second) -> None:
        """
        :param sort_key: how should we sort the peers to get the fastest? low score means top-ranked
        """
        self._waiting_peers = PriorityQueue()
        self._response_command_type = response_command_type
        self._peer_wrapper = SortableTask.orderable_by_func(self._get_peer_rank)
        self._sort_key = sort_key

    def _get_peer_rank(self, peer: TChainPeer) -> float:
        scores = [
            self._sort_key(exchange.tracker)
            for exchange in peer.requests
            if issubclass(exchange.response_cmd_type, self._response_command_type)
        ]

        if len(scores) == 0:
            raise ValidationError(
                f"Could not find any exchanges on {peer} "
                f"with response {self._response_command_type!r}"
            )

        # Typically there will only be one score, but we might want to match multiple commands.
        # To handle that case, we take the average of the scores:
        return sum(scores) / len(scores)

    def put_nowait(self, peer: TChainPeer) -> None:
        self._waiting_peers.put_nowait(self._peer_wrapper(peer))

    async def get_fastest(self) -> TChainPeer:
        wrapped_peer = await self._waiting_peers.get()
        peer = wrapped_peer.original

        # make sure the peer has not gone offline while waiting in the queue
        while not peer.is_operational:
            # if so, look for the next best peer
            wrapped_peer = await self._waiting_peers.get()
            peer = wrapped_peer.original

        return peer
