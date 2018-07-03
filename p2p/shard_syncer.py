from collections import (
    defaultdict,
)
import time
from typing import (
    Any,
    cast,
    Dict,
    Set,
)

from eth_typing import (
    Hash32,
)

from evm.rlp.collations import Collation
from evm.rlp.headers import CollationHeader
from evm.chains.shard import Shard

from evm.db.shard import (
    Availability,
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
from p2p.service import BaseService
from p2p.peer import (
    PeerPool,
    PeerPoolSubscriber,
)

from p2p.sharding_peer import (
    ShardingPeer,
)
from p2p.sharding_protocol import (
    ShardingProtocol,
    Collations,
    GetCollations,
    NewCollationHashes,
)

from p2p.utils import (
    gen_request_id,
)

from cytoolz import (
    excepts,
)


COLLATION_PERIOD = 1


class ShardSyncer(BaseService, PeerPoolSubscriber):

    def __init__(self, shard: Shard, peer_pool: PeerPool, token: CancelToken=None) -> None:
        super().__init__(token)

        self.shard = shard
        self.peer_pool = peer_pool

        self.collation_hashes_at_peer: Dict[ShardingPeer, Set[Hash32]] = defaultdict(set)

        self.start_time = time.time()

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
            cast(ShardingProtocol, peer.sub_proto).send_new_collation_hashes(
                [(collation.hash, collation.period)]
            )

        return collation

    #
    # Peer handling
    #
    async def _run(self) -> None:
        with self.subscribe(self.peer_pool):
            while True:

                peer, cmd, msg = await wait_with_token(
                    self.msg_queue.get(), token=self.cancel_token)

                peer = cast(ShardingPeer, peer)
                msg = cast(Dict[str, Any], msg)
                if isinstance(cmd, GetCollations):
                    await self._handle_get_collations(peer, msg)
                elif isinstance(cmd, Collations):
                    await self._handle_collations(peer, msg)
                elif isinstance(cmd, NewCollationHashes):
                    await self._handle_new_collation_hashes(peer, msg)

    async def _handle_get_collations(self, peer: ShardingPeer, msg: Dict[str, Any]) -> None:
        """Respond with all requested collations that we know about."""
        collation_hashes = set(msg["collation_hashes"])
        self.collation_hashes_at_peer[peer] |= collation_hashes

        get_collation_or_none = excepts(
            (CollationHeaderNotFound, CollationBodyNotFound),
            self.shard.get_collation_by_hash
        )
        collations = [
            collation for collation in [
                get_collation_or_none(collation_hash) for collation_hash in collation_hashes
            ]
            if collation is not None
        ]
        self.logger.info(
            "Responding to peer %s with %d collations",
            peer.remote,
            len(collations),
        )
        peer.sub_proto = cast(ShardingProtocol, peer.sub_proto)
        peer.sub_proto.send_collations(msg["request_id"], collations)

    async def _handle_collations(self, peer: ShardingPeer, msg: Dict[str, Any]) -> None:
        """Add collations to our shard and notify peers about new collations available here."""
        collations_by_hash = {collation.hash: collation for collation in msg["collations"]}
        self.collation_hashes_at_peer[peer] |= set(collations_by_hash.keys())

        # add new collations to shard
        new_collations_by_hash = {
            collation.hash: collation for collation in collations_by_hash.values()
            if self.shard.get_availability(collation.header) is not Availability.AVAILABLE
        }
        self.logger.info(
            "Received %d collations, %d of which are new",
            len(collations_by_hash),
            len(new_collations_by_hash),
        )
        self.logger.info("%s %s", collations_by_hash, new_collations_by_hash)
        for collation in new_collations_by_hash.values():
            self.shard.add_collation(collation)

        # inform peers about new collations they might not know about already
        for pool_peer in self.peer_pool.peers:
            pool_peer = cast(ShardingPeer, pool_peer)
            known_hashes = self.collation_hashes_at_peer[pool_peer]
            new_hashes = set(new_collations_by_hash.keys()) - known_hashes
            self.collation_hashes_at_peer[pool_peer] |= new_hashes

            if new_hashes:
                new_collations = [
                    new_collations_by_hash[collation_hash] for collation_hash in new_hashes
                ]
                hashes_and_periods = [
                    (collation.hash, collation.period) for collation in new_collations
                ]
                pool_peer.sub_proto = cast(ShardingProtocol, pool_peer.sub_proto)
                pool_peer.sub_proto.send_new_collation_hashes(hashes_and_periods)

    async def _handle_new_collation_hashes(self, peer: ShardingPeer, msg: Dict[str, Any]) -> None:
        """Request those collations."""
        # Request all collations for now, no matter if we now about them or not, as there's no way
        # to header existence at the moment. In the future we won't transfer collations anyway but
        # only collation bodies (headers are retrieved from the main chain), so there's no need to
        # add this at the moment.
        collation_hashes = set(
            collation_hash for collation_hash, _ in msg["collation_hashes_and_periods"]
        )
        if collation_hashes:
            peer.sub_proto = cast(ShardingProtocol, peer.sub_proto)
            peer.sub_proto.send_get_collations(gen_request_id(), list(collation_hashes))

    def get_current_period(self) -> int:
        # TODO: get this from main chain
        return int((time.time() - self.start_time) // COLLATION_PERIOD)
