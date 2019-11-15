import asyncio
from collections import Counter
import typing
from typing import (
    Iterable,
    List,
    Set,
    Tuple,
)

from cancel_token import CancelToken, OperationCancelled
from eth.abc import AtomicDatabaseAPI
from eth_typing import Hash32
import rlp

from p2p.exceptions import BaseP2PError, PeerConnectionLost
from p2p.service import BaseService

from trinity.protocol.eth.peer import ETHPeer, ETHPeerPool
from trinity.sync.beam.constants import (
    GAP_BETWEEN_TESTS,
)

from .queen import (
    QueeningQueue,
    QueenTrackerAPI,
)

REQUEST_SIZE = 16


class BeamStateBackfill(BaseService, QueenTrackerAPI):
    """
    Use a very simple strategy to fill in state in the background.

    Ask each peer in sequence for some nodes, ignoring the lowest RTT node.
    Reduce memory pressure by using a depth-first strategy.

    An intended side-effect is to build & maintain an accurate measurement of
    the round-trip-time that peers take to respond to GetNodeData commands.
    """

    _total_processed_nodes = 0
    _num_added = 0
    _num_missed = 0
    _report_interval = 10

    _num_requests_by_peer: typing.Counter[ETHPeer]

    def __init__(
            self,
            db: AtomicDatabaseAPI,
            peer_pool: ETHPeerPool,
            token: CancelToken = None) -> None:

        # in case there is no token set, make sure this gets cancelled when the peer pool does
        if token is None:
            token = peer_pool.cancel_token

        # Init the superclass
        super().__init__(token=token)

        self._db = db

        # Pending nodes to download
        self._node_hashes: List[Hash32] = []

        self._peer_pool = peer_pool
        self._available_peers = asyncio.Event()

        self._is_missing: Set[Hash32] = set()

        self._num_requests_by_peer = Counter()

        self._queening_queue = QueeningQueue(peer_pool, token=token)

    async def get_queen_peer(self) -> ETHPeer:
        return await self._queening_queue.get_queen_peer()

    def penalize_queen(self, peer: ETHPeer) -> None:
        self._queening_queue.penalize_queen(peer)

    async def _run(self) -> None:
        self.run_daemon_task(self._periodically_report_progress())

        self.run_daemon(self._queening_queue)

        await self.wait(self._run_backfill())

    async def _run_backfill(self) -> None:
        while self.is_operational:
            peer = await self._queening_queue.pop_fastest_peasant()

            # collect node hashes that might be missing
            await self._walk()

            self._node_hashes, on_deck = (
                self._node_hashes[:-1 * REQUEST_SIZE],
                tuple(self._node_hashes[-1 * REQUEST_SIZE:]),
            )

            if len(on_deck) == 0:
                # Nothing left to request, break and wait for new data to come in
                self._queening_queue.readd_peasant(peer)
                self.logger.debug("Backfill is waiting for more hashes to arrive")
                await self.sleep(2)
                continue

            self.run_task(self._make_request(peer, on_deck))

    async def _make_request(self, peer: ETHPeer, request_hashes: Tuple[Hash32, ...]) -> None:
        self._num_requests_by_peer[peer] += 1
        try:
            nodes = await peer.eth_api.get_node_data(request_hashes)
        except asyncio.TimeoutError:
            self._node_hashes.extend(request_hashes)
            self._queening_queue.readd_peasant(peer, GAP_BETWEEN_TESTS * 2)
        except (PeerConnectionLost, OperationCancelled):
            # Something unhappy, but we don't really care, peer will be gone by next loop
            self._node_hashes.extend(request_hashes)
        except (BaseP2PError, Exception) as exc:
            self.logger.info("Unexpected err while getting background nodes from %s: %s", peer, exc)
            self.logger.debug("Problem downloading background nodes from peer...", exc_info=True)
            self._node_hashes.extend(request_hashes)
            self._queening_queue.readd_peasant(peer, GAP_BETWEEN_TESTS * 2)
        else:
            self._queening_queue.readd_peasant(peer, GAP_BETWEEN_TESTS)
            self._insert_results(request_hashes, nodes)

    def _insert_results(
            self,
            requested_hashes: Tuple[Hash32, ...],
            nodes: Tuple[Tuple[Hash32, bytes], ...]) -> None:

        returned_nodes = dict(nodes)
        with self._db.atomic_batch() as write_batch:
            for requested_hash in requested_hashes:
                if requested_hash in returned_nodes:
                    self._num_added += 1
                    self._total_processed_nodes += 1
                    encoded_node = returned_nodes[requested_hash]
                    write_batch[requested_hash] = encoded_node
                    self._is_missing.discard(requested_hash)
                    self._node_hashes.extend(self._get_children(encoded_node))
                else:
                    self._num_missed += 1
                    self._node_hashes.append(requested_hash)

    def _has_full_request_worth_of_queued_hashes(self) -> bool:
        if len(self._node_hashes) < REQUEST_SIZE:
            # there are too few hashes available
            return False

        next_request_preview = self._node_hashes[-1 * REQUEST_SIZE:]

        # confirm that all queued hashes are missing from the database
        # self._is_missing is cached to avoid excessive I/O of checking repeatedly
        return all(node_hash not in self._is_missing for node_hash in next_request_preview)

    async def _walk(self) -> None:
        """
        Evaluate queued node hashes, checking which ones are locally available. For
        anything that is locally available, load it up and put its children on the queue.
        """
        while not self._has_full_request_worth_of_queued_hashes():
            for reversed_idx, node_hash in enumerate(reversed(self._node_hashes)):
                if node_hash in self._is_missing:
                    continue

                try:
                    encoded_node = self._db[node_hash]
                except KeyError:
                    self._is_missing.add(node_hash)
                    # release the event loop, because doing a bunch of db reads is slow
                    await self.sleep(0)
                    continue
                else:
                    # found a node to expand out
                    remove_idx = len(self._node_hashes) - reversed_idx - 1
                    break
            else:
                # Didn't find any nodes to expand. Give up the walk
                return

            # remove the already-present node hash
            del self._node_hashes[remove_idx]

            # Expand out the node that's already present
            self._node_hashes.extend(self._get_children(encoded_node))

            # Release the event loop, because this could be long
            await self.sleep(0)

            # Continue until the pending stack is big enough

    def _get_children(self, encoded_node: bytes) -> Iterable[Hash32]:
        try:
            decoded_node = rlp.decode(encoded_node)
        except rlp.DecodingError:
            # Could not decode rlp, it's probably a bytecode, carry on...
            return set()

        if len(decoded_node) == 17:
            # branch node
            return set(node_hash for node_hash in decoded_node[:16] if len(node_hash) == 32)
        elif len(decoded_node) == 2 and len(decoded_node[1]) == 32:
            # leaf or extension node
            return {decoded_node[1]}
        else:
            # final value, ignore
            return set()

    def set_root_hash(self, root_hash: Hash32) -> None:
        if len(self._node_hashes) < REQUEST_SIZE:
            self._node_hashes.append(root_hash)

    async def _periodically_report_progress(self) -> None:
        while self.is_operational:
            await self.sleep(self._report_interval)

            if len(self._node_hashes) == 0:
                self.logger.debug("Beam-Backfill: waiting for new state root")
                continue

            msg = "all=%d" % self._total_processed_nodes
            msg += "  new=%d" % self._num_added
            msg += "  missed=%d" % self._num_missed
            msg += "  queen=%s" % self._queening_queue.queen
            self.logger.debug("Beam-Backfill: %s", msg)

            self._num_added = 0
            self._num_missed = 0

            # log peer counts
            show_top_n_peers = 3
            self.logger.debug(
                "Beam-Backfill-Peer-Usage-Top-%d: %s",
                show_top_n_peers,
                self._num_requests_by_peer.most_common(show_top_n_peers),
            )
            self._num_requests_by_peer.clear()
