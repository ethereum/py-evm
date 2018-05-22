import asyncio
import logging
import time
from typing import (
    cast,
    Dict,
    List,
    Set,
    Tuple,
)

from eth_typing import (
    Hash32,
)

import rlp
from rlp import sedes
from rlp.sedes import (
    big_endian_int,
)

from evm.rlp.collations import Collation
from evm.rlp.headers import CollationHeader
from evm.rlp.sedes import (
    hash32,
)
from evm.chains.shard import Shard

from evm.db.backends.memory import MemoryDB
from evm.db.shard import (
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
from evm.exceptions import (
    CollationHeaderNotFound,
    CollationBodyNotFound,
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
from p2p.utils import (
    gen_request_id,
)
from p2p.exceptions import (
    HandshakeFailure,
    OperationCancelled,
    UnexpectedMessage,
)


COLLATION_PERIOD = 1


class Status(Command):
    _cmd_id = 0


class Collations(Command):
    _cmd_id = 1

    structure = [
        ("request_id", sedes.big_endian_int),
        ("collations", sedes.CountableList(Collation)),
    ]


class GetCollations(Command):
    _cmd_id = 2

    structure = [
        ("request_id", sedes.big_endian_int),
        ("collation_hashes", sedes.CountableList(hash32)),
    ]


class NewCollationHashes(Command):
    _cmd_id = 3

    structure = [
        ("collation_hashes_and_periods", rlp.sedes.List([hash32, big_endian_int]))
    ]


class ShardingProtocol(Protocol):
    name = "sha"
    version = 0
    _commands = [Status, Collations, GetCollations, NewCollationHashes]
    cmd_length = 4

    logger = logging.getLogger("p2p.sharding.ShardingProtocol")

    def send_handshake(self) -> None:
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending status msg")
        self.send(*cmd.encode([]))

    def send_collations(self, request_id: int, collations: List[Collation]) -> None:
        cmd = Collations(self.cmd_id_offset)
        self.logger.debug("Sending %d collations (request id %d)", len(collations), request_id)
        data = {
            "request_id": request_id,
            "collations": collations,
        }
        self.send(*cmd.encode(data))

    def send_get_collations(self, request_id: int, collation_hashes: List[Hash32]) -> None:
        cmd = GetCollations(self.cmd_id_offset)
        self.logger.debug(
            "Requesting %d collations (request id %d)",
            len(collation_hashes),
            request_id,
        )
        data = {
            "request_id": request_id,
            "collation_hashes": collation_hashes,
        }
        self.send(*cmd.encode(data))

    def send_new_collation_hashes(self,
                                  collation_hashes_and_periods: List[Tuple[Hash32, int]]) -> None:
        cmd = NewCollationHashes(self.cmd_id_offset)
        self.logger.debug(
            "Announcing %d new collations (period %d to %d)",
            len(collation_hashes_and_periods),
            min(period for _, period in collation_hashes_and_periods),
            max(period for _, period in collation_hashes_and_periods)
        )
        data = {
            "collation_hashes_and_periods": collation_hashes_and_periods
        }
        self.send(*cmd.encode(data))


class ShardingPeer(BasePeer):
    _supported_sub_protocols = [ShardingProtocol]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.known_collation_hashes: Set[Hash32] = set()
        self._pending_replies: Dict[int, asyncio.Event] = {}

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
    # Message handling
    #
    def handle_sub_proto_msg(self, cmd: Command, msg: protocol._DecodedMsgType) -> None:
        if isinstance(msg, dict):
            request_id = msg.get("request_id")
            if request_id is not None and request_id in self._pending_replies:
                # This is a reply we're waiting for, so we consume it by resolving the registered
                # future
                future = self._pending_replies.pop(request_id)
                future.set_result((cmd, msg))
                return
        super().handle_sub_proto_msg(cmd, msg)

    #
    # Requests
    #
    async def get_collations(self,
                             collation_hashes: List[Hash32],
                             cancel_token: CancelToken) -> Set[Collation]:
        # Don't send empty request
        if len(collation_hashes) == 0:
            return set()

        request_id = gen_request_id()
        pending_reply = asyncio.Future()
        self._pending_replies[request_id] = pending_reply
        self.sub_proto.send_get_collations(request_id, collation_hashes)
        cmd, msg = await wait_with_token(pending_reply, token=cancel_token)

        if not isinstance(cmd, Collations):
            raise UnexpectedMessage(
                "Expected Collations as response to GetCollations, but got %s",
                cmd.__class__.__name__
            )
        return set(msg["collations"])


class ShardSyncer(BaseService, PeerPoolSubscriber):
    logger = logging.getLogger("p2p.sharding.ShardSyncer")

    def __init__(self, shard: Shard, peer_pool: PeerPool, token: CancelToken=None) -> None:
        super().__init__(token)

        self.shard = shard
        self.peer_pool = peer_pool
        self._running_peers: Set[ShardingPeer] = set()

        self.collations_received_event = asyncio.Event()

        self.start_time = time.time()

    async def _run(self) -> None:
        with self.subscribe(self.peer_pool):
            await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        pass

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
            peer.sub_proto.send_collations(gen_request_id(), [collation])

        return collation

    #
    # Peer handling
    #
    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(ShardingPeer, peer)))

    async def handle_peer(self, peer: ShardingPeer) -> None:
        self._running_peers.add(peer)
        try:
            await self._handle_peer(peer)
        finally:
            self._running_peers.remove(peer)

    async def _handle_peer(self, peer: ShardingPeer) -> None:
        while not self.is_finished:
            try:
                self.logger.info("%s waiting for message", peer.remote)
                cmd, msg = await peer.read_sub_proto_msg(self.cancel_token)
            except OperationCancelled:
                # Either the peer disconnected or our cancel_token has been triggered, so break
                # out of the loop to stop attempting to sync with this peer.
                break

            if isinstance(cmd, GetCollations):  # respond to collation requests
                # TODO: limit number of hashes
                collations = []
                for collation_hash in set(msg["collation_hashes"]):
                    try:
                        collation = self.shard.get_collation_by_hash(collation_hash)
                    except (CollationHeaderNotFound, CollationBodyNotFound):
                        continue
                    else:
                        collations.append(collation)
                self.logger.info(
                    "Responding to peer %s with %d collations",
                    peer.remote,
                    len(collations)
                )
                peer.sub_proto.send_collations(msg["request_id"], collations)

        await peer.cancel()
        self.logger.debug("%s finished", peer)

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
