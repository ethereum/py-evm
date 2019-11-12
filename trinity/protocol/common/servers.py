from abc import abstractmethod
from typing import (
    Any,
    AsyncIterator,
    Iterable,
    Tuple,
    Type,
)

from cancel_token import CancelToken, OperationCancelled

from lahja import EndpointAPI

from eth_typing import Hash32
from eth_utils import get_extended_debug_logger

from eth.exceptions import (
    HeaderNotFound,
)
from eth_typing import (
    BlockNumber,
)
from eth.rlp.headers import BlockHeader
from lahja import (
    BroadcastConfig,
)

from p2p.abc import CommandAPI, SessionAPI
from p2p.cancellable import CancellableMixin
from p2p.peer import (
    BasePeer,
    PeerSubscriber,
)
from p2p.service import BaseService

from trinity._utils.headers import sequence_builder
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.peer import BasePeerPool
from trinity.protocol.common.payloads import BlockHeadersQuery

from .events import PeerPoolMessageEvent


class BaseRequestServer(BaseService, PeerSubscriber):
    """
    Monitor commands from peers, to identify inbound requests that should receive a response.
    Handle those inbound requests by querying our local database and replying.
    """
    # This is a rather arbitrary value, but when the sync is operating normally we never see
    # the msg queue grow past a few hundred items, so this should be a reasonable limit for
    # now.
    msg_queue_maxsize = 2000

    def __init__(
            self,
            peer_pool: BasePeerPool,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self._peer_pool = peer_pool

    async def _run(self) -> None:
        self.run_daemon_task(self._handle_msg_loop())
        with self.subscribe(self._peer_pool):
            await self.cancellation()

    async def _handle_msg_loop(self) -> None:
        while self.is_operational:
            peer, cmd = await self.wait(self.msg_queue.get())
            self.run_task(self._quiet_handle_msg(peer, cmd))

    async def _quiet_handle_msg(
            self,
            peer: BasePeer,
            cmd: CommandAPI[Any]) -> None:
        try:
            await self._handle_msg(peer, cmd)
        except OperationCancelled:
            # Silently swallow OperationCancelled exceptions because otherwise they'll be caught
            # by the except below and treated as unexpected.
            pass
        except Exception:
            self.logger.exception("Unexpected error when processing msg from %s", peer)

    @abstractmethod
    async def _handle_msg(self, peer: BasePeer, cmd: CommandAPI[Any]) -> None:
        """
        Identify the command, and react appropriately.
        """
        ...


class BaseIsolatedRequestServer(BaseService):
    """
    Monitor commands from peers, to identify inbound requests that should receive a response.
    Handle those inbound requests by querying our local database and replying.
    """

    def __init__(
            self,
            event_bus: EndpointAPI,
            broadcast_config: BroadcastConfig,
            subscribed_events: Iterable[Type[PeerPoolMessageEvent]],
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.event_bus = event_bus
        self.broadcast_config = broadcast_config
        self._subscribed_events = subscribed_events

    async def _run(self) -> None:

        for event_type in self._subscribed_events:
            self.run_daemon_task(self.handle_stream(event_type))

        await self.cancellation()

    async def handle_stream(self, event_type: Type[PeerPoolMessageEvent]) -> None:
        while self.is_operational:
            async for event in self.wait_iter(self.event_bus.stream(event_type)):
                self.run_task(self._quiet_handle_msg(event.session, event.command))

    async def _quiet_handle_msg(
            self,
            session: SessionAPI,
            cmd: CommandAPI[Any]) -> None:
        try:
            await self._handle_msg(session, cmd)
        except OperationCancelled:
            # Silently swallow OperationCancelled exceptions because otherwise they'll be caught
            # by the except below and treated as unexpected.
            pass
        except Exception:
            self.logger.exception("Unexpected error when processing msg from %s", session)

    @abstractmethod
    async def _handle_msg(self,
                          session: SessionAPI,
                          cmd: CommandAPI[Any]) -> None:
        ...


class BasePeerRequestHandler(CancellableMixin):
    logger = get_extended_debug_logger('trinity.protocol.common.servers.PeerRequestHandler')

    def __init__(self, db: BaseAsyncHeaderDB, token: CancelToken) -> None:
        self.db = db
        self.cancel_token = token

    async def lookup_headers(self,
                             query: BlockHeadersQuery) -> Tuple[BlockHeader, ...]:
        """
        Lookup :max_headers: headers starting at :block_number_or_hash:, skipping :skip: items
        between each, in reverse order if :reverse: is True.
        """
        try:
            block_numbers = await self._get_block_numbers_for_query(query)
        except HeaderNotFound:
            self.logger.debug(
                "Peer requested starting header %r that is unavailable, returning nothing",
                query.block_number_or_hash)
            return tuple()

        headers: Tuple[BlockHeader, ...] = tuple([
            header
            async for header
            in self._generate_available_headers(block_numbers)
        ])
        return headers

    async def _get_block_numbers_for_query(self,
                                           query: BlockHeadersQuery,
                                           ) -> Tuple[BlockNumber, ...]:
        """
        Generate the block numbers for a given `HeaderRequest`.
        """
        if isinstance(query.block_number_or_hash, bytes):
            header = await self.wait(
                self.db.coro_get_block_header_by_hash(Hash32(query.block_number_or_hash)))
            start_number = header.block_number
        elif isinstance(query.block_number_or_hash, int):
            start_number = query.block_number_or_hash
        else:
            actual_type = type(query.block_number_or_hash)
            raise TypeError(f"Invariant: unexpected type for 'block_number_or_hash': {actual_type}")

        return sequence_builder(
            start_number=start_number,
            max_length=query.max_headers,
            skip=query.skip,
            reverse=query.reverse,
        )

    async def _generate_available_headers(
            self, block_numbers: Tuple[BlockNumber, ...]) -> AsyncIterator[BlockHeader]:
        """
        Generates the headers requested, halting on the first header that is not locally available.
        """
        for block_num in block_numbers:
            try:
                yield await self.wait(
                    self.db.coro_get_canonical_block_header_by_number(block_num))
            except HeaderNotFound:
                self.logger.debug(
                    "Peer requested header number %s that is unavailable, stopping search.",
                    block_num,
                )
                break
