import asyncio
import logging
import random
import time
from typing import (
    List,
)

import rlp

from evm.rlp.collations import Collation
from evm.rlp.headers import CollationHeader
from evm.chains.shard import Shard

from evm.db.shard import (
    Availability,
)

from p2p.cancel_token import (
    CancelToken,
    wait_with_token,
)
from p2p import protocol
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
        self.logger.debug("Sending {} collations".format(len(collations)))
        self.send(*cmd.encode(collations))


class ShardingPeer(BasePeer):
    _supported_sub_protocols = [ShardingProtocol]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.incoming_collation_queue = None
        self.known_collation_hashes = set()

    def set_incoming_collation_queue(self, queue: asyncio.Queue) -> None:
        self.incoming_collation_queue = queue

    #
    # Handshake
    #
    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake()

    async def process_sub_proto_handshake(
        self,
        cmd: Command,
        msg: protocol._DecodedMsgType
    ) -> None:
        if not isinstance(cmd, Status):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure("Expected status msg, got {}, disconnecting".format(cmd))

    #
    # Receiving Collations
    #
    def handle_sub_proto_msg(self, cmd: Command, msg: protocol._DecodedMsgType) -> None:
        if isinstance(cmd, Collations):
            self._handle_collations_msg(msg)
        else:
            super().handle_sub_proto_msg(cmd, msg)

    def _handle_collations_msg(self, msg: List[Collation]) -> None:
        for collation in msg:
            self.known_collation_hashes.add(collation.hash)
            print(self.known_collation_hashes)
            if self.incoming_collation_queue is not None:
                self.incoming_collation_queue.put_nowait(collation)

    def send_collations(self, collations: List[Collation]) -> None:
        for collation in collations:
            if collation.hash not in self.known_collation_hashes:
                self.known_collation_hashes.put(collation.hash)
                self.sub_proto.send_collations(collations)


class ShardSyncer(PeerPoolSubscriber):

    def __init__(
        self,
        shard: Shard,
        mean_proposing_period: int,
        peer_pool: PeerPool,
        token: CancelToken = None,
    ) -> None:
        self.shard = shard
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)

        self.mean_proposing_period = mean_proposing_period

        self.collations_received_event = asyncio.Future()
        self.collations_proposed_event = asyncio.Future()

        self.incoming_collation_queue = asyncio.Queue()

        self.cancel_token = CancelToken("ShardSyncer")
        if token is not None:
            self.cancel_token = self.cancel_token.chain(token)

    async def run(self) -> None:
        await asyncio.gather(
            self.run_syncer(),
            self.run_proposer(),
        )

    async def run_syncer(self) -> None:
        while True:
            collation = await wait_with_token(
                self.incoming_collation_queue.get(),
                token=self.cancel_token
            )

            if collation.shard_id != self.shard.shard_id:
                continue

            self.shard.add_collation(collation)
            self.collations_received_event.set()
            self.collations_received_event.clear()
            for peer in self.peer_pool.peers:
                peer.send_collations([collation])

    async def run_proposer(self) -> None:
        while True:
            sleep_time = random.expovariate(1 / self.mean_proposing_period)
            await asyncio.sleep(sleep_time)

            # create collation for current period if there isn't one yet
            period = self.get_current_period()
            try:
                existing_header = self.shard.get_header_by_period(period)
            except KeyError:
                existing_header = None

            if existing_header:
                available = self.shard.get_availability(existing_header) is Availability.AVAILABLE
            else:
                available = False

            if existing_header is None or not available:
                header = CollationHeader(self.shard.shard_id, b"\x00" * 32, period, b"\x11" * 20)
                collation = Collation(header, b"body")
                self.collations_proposed_event.set()
                self.collations_proposed_event.clear()

                # broadcast collation
                for peer in self.peer_pool.peers:
                    peer.send_collations([collation])

    def register_peer(self, peer):
        peer.set_incoming_collation_queue(self.incoming_collation_queue)

    def get_current_period(self):
        return int(time.time() // COLLATION_PERIOD)
