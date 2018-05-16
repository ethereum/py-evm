import asyncio
import logging
import time
from typing import (
    cast,
    List,
    Set,
)

from eth_typing import (
    Hash32,
)

import rlp

from evm.rlp.collations import Collation
from evm.rlp.headers import CollationHeader
from evm.chains.shard import Shard

from evm.db.backends.memory import MemoryDB
from evm.db.shard import (
    Availability,
    ShardDB,
)

from evm.utils.padding import (
    zpad_right,
)
from evm.utils.blobs import (
    calc_chunk_root,
)

from evm.constants import (
    COLLATION_SIZE,
)

from p2p.cancel_token import (
    CancelToken,
    wait_with_token,
)
from p2p.discovery import DiscoveryProtocol
from p2p import protocol
from p2p.server import Server
from p2p.service import BaseService
from p2p.protocol import (
    Command,
    Protocol,
)
from p2p.peer import (
    BasePeer,
    PeerPool,
    PeerPoolSubscriber,
)
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.exceptions import (
    HandshakeFailure,
    OperationCancelled,
)


COLLATION_PERIOD = 1


class Status(Command):
    _cmd_id = 0


class Collations(Command):
    _cmd_id = 1

    structure = rlp.sedes.CountableList(Collation)


class ShardingProtocol(Protocol):
    name = "sha"
    version = 0
    _commands = [Status, Collations]
    cmd_length = 2

    logger = logging.getLogger("p2p.sharding.ShardingProtocol")

    def send_handshake(self) -> None:
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending status msg")
        self.send(*cmd.encode([]))

    def send_collations(self, collations: List[Collation]) -> None:
        cmd = Collations(self.cmd_id_offset)
        self.logger.debug("Sending %d collations", len(collations))
        self.send(*cmd.encode(collations))


class ShardingPeer(BasePeer):
    _supported_sub_protocols = [ShardingProtocol]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.incoming_collation_queue: asyncio.Queue[Collation] = asyncio.Queue()
        self.known_collation_hashes: Set[Hash32] = set()

    #
    # Handshake
    #
    async def send_sub_proto_handshake(self) -> None:
        cast(ShardingProtocol, self.sub_proto).send_handshake()

    async def process_sub_proto_handshake(self,
                                          cmd: Command,
                                          msg: protocol._DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure("Expected status msg, got {}, disconnecting".format(cmd))

    #
    # Receiving Collations
    #
    def handle_sub_proto_msg(self, cmd: Command, msg: protocol._DecodedMsgType) -> None:
        if isinstance(cmd, Collations):
            self._handle_collations_msg(cast(List[Collation], msg))
        else:
            super().handle_sub_proto_msg(cmd, msg)

    def _handle_collations_msg(self, msg: List[Collation]) -> None:
        self.logger.debug("Received %d collations", len(msg))
        for collation in msg:
            try:
                self.incoming_collation_queue.put_nowait(collation)
            except asyncio.QueueFull:
                self.logger.warning("Incoming collation queue full, dropping received collation")
            else:
                self.known_collation_hashes.add(collation.hash)

    def send_collations(self, collations: List[Collation]) -> None:
        self.logger.debug("Sending %d collations", len(collations))
        for collation in collations:
            if collation.hash not in self.known_collation_hashes:
                self.known_collation_hashes.add(collation.hash)
                cast(ShardingProtocol, self.sub_proto).send_collations(collations)


class ShardSyncer(BaseService, PeerPoolSubscriber):
    logger = logging.getLogger("p2p.sharding.ShardSyncer")

    def __init__(self, shard: Shard, peer_pool: PeerPool, token: CancelToken=None) -> None:
        super().__init__(token)

        self.shard = shard
        self.peer_pool = peer_pool

        self.incoming_collation_queue: asyncio.Queue[Collation] = asyncio.Queue()

        self.collations_received_event = asyncio.Event()

        self.start_time = time.time()

    async def _run(self) -> None:
        self.peer_pool.subscribe(self)
        while True:
            collation = await wait_with_token(
                self.incoming_collation_queue.get(),
                token=self.cancel_token
            )

            if collation.shard_id != self.shard.shard_id:
                self.logger.debug("Ignoring received collation belonging to wrong shard")
                continue
            if self.shard.get_availability(collation.header) is Availability.AVAILABLE:
                self.logger.debug("Ignoring already available collation")
                continue

            self.logger.debug("Adding collation {} to shard".format(collation))
            self.shard.add_collation(collation)
            for peer in self.peer_pool.peers:
                cast(ShardingPeer, peer).send_collations([collation])

            self.collations_received_event.set()
            self.collations_received_event.clear()

    async def _cleanup(self) -> None:
        self.peer_pool.unsubscribe(self)

    def propose(self) -> Collation:
        """Broadcast a new collation to the network, add it to the local shard, and return it."""
        # create collation for current period
        period = self.get_current_period()
        body = zpad_right(str(self).encode("utf-8"), COLLATION_SIZE)
        header = CollationHeader(self.shard.shard_id, calc_chunk_root(body), period, b"\x11" * 20)
        collation = Collation(header, body)

        self.logger.debug("Proposing collation {}".format(collation))

        # add collation to local chain
        self.shard.add_collation(collation)

        # broadcast collation
        for peer in self.peer_pool.peers:
            cast(ShardingPeer, peer).send_collations([collation])

        return collation

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(ShardingPeer, peer)))

    async def handle_peer(self, peer: ShardingPeer) -> None:
        while not self.is_finished:
            try:
                collation = await wait_with_token(
                    peer.incoming_collation_queue.get(),
                    token=self.cancel_token
                )
                await wait_with_token(
                    self.incoming_collation_queue.put(collation),
                    token=self.cancel_token
                )
            except OperationCancelled:
                break  # stop handling peer if cancel token is triggered

    def get_current_period(self):
        # TODO: get this from main chain
        return int((time.time() - self.start_time) // COLLATION_PERIOD)


class ShardingServer(Server):

    def _make_peer_pool(self, discovery: DiscoveryProtocol) -> PeerPool:
        # XXX: This is not supposed to work and causes both the PeerPool and Server to crash, but
        # the tests in test_sharding.py don't seem to care
        headerdb = None
        return self.peer_pool_class(
            self.peer_class,
            headerdb,
            self.network_id,
            self.privkey,
            discovery,
            min_peers=self.min_peers,
        )

    def _make_syncer(self, peer_pool: PeerPool) -> BaseService:
        shard_db = ShardDB(MemoryDB())
        shard = Shard(shard_db, 0)
        return ShardSyncer(shard, peer_pool, self.cancel_token)
