import asyncio
from contextlib import contextmanager
from typing import (
    AsyncIterator,
    Iterator,
    Set,
)

from cancel_token import CancelToken
from eth_utils import ValidationError

from p2p.exceptions import NoConnectedPeers
from p2p.peer import BasePeer, PeerSubscriber
from p2p.service import BaseService

from trinity.protocol.common.peer import BaseChainPeer, BaseChainPeerPool


class BaseChainTipMonitor(BaseService, PeerSubscriber):
    """
    Monitor for potential changes to the tip of the chain: a new peer or a new block

    Subclass must specify :attr:`subscription_msg_types`
    """
    # This is a rather arbitrary value, but when the sync is operating normally we never see
    # the msg queue grow past a few hundred items, so this should be a reasonable limit for
    # now.
    msg_queue_maxsize = 2000

    def __init__(
            self,
            peer_pool: BaseChainPeerPool,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self._peer_pool = peer_pool
        # There is one event for each subscriber, each one gets set any time new tip info arrives
        self._subscriber_notices: Set[asyncio.Event] = set()

    async def wait_tip_info(self) -> AsyncIterator[BaseChainPeer]:
        """
        This iterator waits until there is potentially new tip information.
        New tip information means a new peer connected or a new block arrived.
        Then it yields the peer with the highest total difficulty.
        It continues indefinitely, until this service is cancelled.
        """
        if self.is_cancelled:
            raise ValidationError("%s is cancelled, new tip info is impossible", self)
        elif not self.is_running:
            await self.events.started.wait()

        with self._subscriber() as new_tip_event:
            while self.is_operational:
                try:
                    highest_td_peer = self._peer_pool.highest_td_peer
                except NoConnectedPeers:
                    # no peers are available right now, skip the new tip info yield
                    pass
                else:
                    yield highest_td_peer

                await self.wait(new_tip_event.wait())
                new_tip_event.clear()

    def register_peer(self, peer: BasePeer) -> None:
        self._notify_tip()

    async def _handle_msg_loop(self) -> None:
        new_tip_types = tuple(self.subscription_msg_types)
        while self.is_operational:
            peer, cmd, msg = await self.wait(self.msg_queue.get())
            if isinstance(cmd, new_tip_types):
                self._notify_tip()

    def _notify_tip(self) -> None:
        for new_tip_event in self._subscriber_notices:
            new_tip_event.set()

    async def _run(self) -> None:
        self.run_daemon_task(self._handle_msg_loop())
        with self.subscribe(self._peer_pool):
            await self.cancellation()

    @contextmanager
    def _subscriber(self) -> Iterator[asyncio.Event]:
        new_tip_event = asyncio.Event()
        self._subscriber_notices.add(new_tip_event)
        try:
            yield new_tip_event
        finally:
            self._subscriber_notices.remove(new_tip_event)
