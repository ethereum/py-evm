import asyncio
import logging
import operator
import time
from typing import Any, Awaitable, Callable, cast, Dict, List, Set, Tuple  # noqa: F401

from cytoolz import partition_all

from evm.constants import EMPTY_UNCLE_HASH
from evm.db.chain import AsyncChainDB
from evm.db.trie import make_trie_root_and_nodes
from evm.rlp.headers import BlockHeader
from p2p import protocol
from p2p import eth
from p2p.cancel_token import CancelToken, wait_with_token
from p2p.exceptions import OperationCancelled
from p2p.peer import BasePeer, ETHPeer, PeerPool, PeerPoolSubscriber


class ChainSyncer(PeerPoolSubscriber):
    logger = logging.getLogger("p2p.chain.ChainSyncer")
    # We'll only sync if we are connected to at least min_peers_to_sync.
    min_peers_to_sync = 2
    _reply_timeout = 5

    def __init__(self, chaindb: AsyncChainDB, peer_pool: PeerPool) -> None:
        self.chaindb = chaindb
        self.peer_pool = peer_pool
        self.peer_pool.min_peers = self.min_peers_to_sync
        self.peer_pool.subscribe(self)
        self.cancel_token = CancelToken('ChainSyncer')
        self._running_peers = set()  # type: Set[ETHPeer]
        self._syncing = False
        self._sync_requests = asyncio.Queue()  # type: asyncio.Queue[ETHPeer]
        self._new_headers = asyncio.Queue()  # type: asyncio.Queue[List[BlockHeader]]
        self._body_requests = asyncio.Queue()  # type: asyncio.Queue[List[BlockHeader]]
        self._receipt_requests = asyncio.Queue()  # type: asyncio.Queue[List[BlockHeader]]
        # A mapping from (transaction_root, uncles_hash) to (block_header, request time) so that
        # we can keep track of pending block bodies and retry them when necessary.
        self._pending_bodies = {}  # type: Dict[Tuple[bytes, bytes], Tuple[BlockHeader, float]]
        # A mapping from receipt_root to (block_header, request time) so that we can keep track of
        # pending block receipts and retry them when necessary.
        self._pending_receipts = {}  # type: Dict[bytes, Tuple[BlockHeader, float]]
        asyncio.ensure_future(self.body_downloader())
        asyncio.ensure_future(self.receipt_downloader())

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(ETHPeer, peer)))
        highest_td_peer = max(
            [cast(ETHPeer, peer) for peer in self.peer_pool.peers],
            key=operator.attrgetter('head_td'))
        self._sync_requests.put_nowait(highest_td_peer)

    async def handle_peer(self, peer: ETHPeer) -> None:
        """Handle the lifecycle of the given peer."""
        self._running_peers.add(peer)
        try:
            await self._handle_peer(peer)
        finally:
            self._running_peers.remove(peer)

    async def _handle_peer(self, peer: ETHPeer) -> None:
        while True:
            try:
                cmd, msg = await peer.read_sub_proto_msg(self.cancel_token)
            except OperationCancelled:
                # Either our cancel token or the peer's has been triggered, so break out of the
                # loop.
                break

            try:
                await self.handle_msg(peer, cmd, msg)
            except Exception as e:
                self.logger.error("Unexpected error when processing msg from %s: %s", peer, repr(e))
                break

    async def run(self) -> None:
        while True:
            try:
                peer = await wait_with_token(
                    self._sync_requests.get(),
                    token=self.cancel_token)
            except OperationCancelled:
                break

            asyncio.ensure_future(self.sync(peer))

            # TODO: If we're in light mode and we've synced up to head - 1024, wait until there's
            # no more pending bodies/receipts, trigger cancel token to stop and raise an exception
            # to tell our caller it should perform a state sync.

    async def sync(self, peer: ETHPeer) -> None:
        if self._syncing:
            self.logger.debug(
                "Got a NewBlock or a new peer, but already syncing so doing nothing")
            return
        elif len(self._running_peers) < self.min_peers_to_sync:
            self.logger.debug(
                "Connected to less peers (%d) than the minimum (%d) required to sync, "
                "doing nothing", len(self._running_peers), self.min_peers_to_sync)
            return

        self._syncing = True
        try:
            await self._sync(peer)
        finally:
            self._syncing = False

    async def _sync(self, peer: ETHPeer) -> None:
        head = await self.chaindb.coro_get_canonical_head()
        head_td = await self.chaindb.coro_get_score(head.hash)
        if peer.head_td <= head_td:
            self.logger.debug(
                "Head TD (%d) announced by %s not higher than ours (%d), not syncing",
                peer.head_td, peer, head_td)
            return

        # FIXME: Fetch a batch of headers, in reverse order, starting from our current head, and
        # find the common ancestor between our chain and the peer's.
        start_at = max(0, head.block_number - eth.MAX_HEADERS_FETCH)
        self.logger.debug("Asking %s for header batch starting at %d", peer, start_at)
        peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)
        max_consecutive_timeouts = 3
        consecutive_timeouts = 0
        while True:
            try:
                headers = await wait_with_token(
                    self._new_headers.get(), peer.wait_until_finished(),
                    token=self.cancel_token,
                    timeout=3)
            except OperationCancelled:
                break
            except TimeoutError:
                self.logger.debug("Timeout waiting for header batch from %s", peer)
                consecutive_timeouts += 1
                if consecutive_timeouts > max_consecutive_timeouts:
                    self.logger.debug(
                        "Too many consecutive timeouts waiting for header batch, aborting sync "
                        "with %s", peer)
                    break
                continue

            if peer.is_finished():
                self.logger.debug("%s disconnected, stopping sync", peer)
                break

            consecutive_timeouts = 0
            if headers[-1].block_number <= start_at:
                self.logger.debug(
                    "Ignoring headers from %d to %d as they've been processed already",
                    headers[0].block_number, headers[-1].block_number)
                continue

            # TODO: Process headers for consistency.
            for header in headers:
                await self.chaindb.coro_persist_header(header)
                start_at = header.block_number

            self._body_requests.put_nowait(headers)
            self._receipt_requests.put_nowait(headers)

            self.logger.debug("Asking %s for header batch starting at %d", peer, start_at)
            # TODO: Instead of requesting sequential batches from a single peer, request a header
            # skeleton and make concurrent requests, using as many peers as possible, to fill the
            # skeleton.
            peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)

    async def _downloader(self,
                          queue: 'asyncio.Queue[List[BlockHeader]]',
                          should_skip: Callable[[BlockHeader], bool],
                          request_func: Callable[[List[BlockHeader]], Awaitable[None]],
                          pending: Dict[Any, Tuple[BlockHeader, float]]) -> None:
        while True:
            try:
                headers = await wait_with_token(
                    queue.get(),
                    token=self.cancel_token,
                    timeout=self._reply_timeout)
            except TimeoutError:
                # We use a timeout above to make sure we periodically retry timedout items
                # even when there's no new items coming through.
                pass
            except OperationCancelled:
                return
            else:
                await request_func(
                    [header for header in headers if not should_skip(header)])

            await self._retry_timedout(request_func, pending)

    async def _retry_timedout(self,
                              request_func: Callable[[List[BlockHeader]], Awaitable[None]],
                              pending: Dict[Any, Tuple[BlockHeader, float]]) -> None:
        now = time.time()
        timed_out = [
            header
            for header, req_time
            in pending.values()
            if now - req_time > self._reply_timeout
        ]
        if timed_out:
            self.logger.debug("Re-requesting %d timed out block parts...", len(timed_out))
            await request_func(timed_out)

    async def body_downloader(self) -> None:
        await self._downloader(
            self._body_requests,
            self._should_skip_body_download,
            self.request_bodies,
            self._pending_bodies)

    async def receipt_downloader(self) -> None:
        await self._downloader(
            self._receipt_requests,
            self._should_skip_receipts_download,
            self.request_receipts,
            self._pending_receipts)

    def _should_skip_body_download(self, header: BlockHeader) -> bool:
        return (header.transaction_root == self.chaindb.empty_root_hash and
                header.uncles_hash == EMPTY_UNCLE_HASH)

    async def request_bodies(self, headers: List[BlockHeader]) -> None:
        for batch in partition_all(eth.MAX_BODIES_FETCH, headers):
            peer = await self.peer_pool.get_random_peer()
            cast(ETHPeer, peer).sub_proto.send_get_block_bodies([header.hash for header in batch])
            self.logger.debug("Requesting %d block bodies to %s", len(batch), peer)
            now = time.time()
            for header in batch:
                key = (header.transaction_root, header.uncles_hash)
                self._pending_bodies[key] = (header, now)

    def _should_skip_receipts_download(self, header: BlockHeader) -> bool:
        return header.receipt_root == self.chaindb.empty_root_hash

    async def request_receipts(self, headers: List[BlockHeader]) -> None:
        for batch in partition_all(eth.MAX_RECEIPTS_FETCH, headers):
            peer = await self.peer_pool.get_random_peer()
            cast(ETHPeer, peer).sub_proto.send_get_receipts([header.hash for header in batch])
            self.logger.debug("Requesting %d block receipts to %s", len(batch), peer)
            now = time.time()
            for header in batch:
                self._pending_receipts[header.receipt_root] = (header, now)

    async def wait_until_finished(self) -> None:
        start_at = time.time()
        # Wait at most 5 seconds for pending peers to finish.
        self.logger.info("Waiting for %d running peers to finish", len(self._running_peers))
        while time.time() < start_at + 5:
            if not self._running_peers:
                break
            await asyncio.sleep(0.1)
        else:
            self.logger.info("Waited too long for peers to finish, exiting anyway")

    async def stop(self) -> None:
        self.cancel_token.trigger()
        self.peer_pool.unsubscribe(self)
        await self.wait_until_finished()

    async def handle_msg(self, peer: ETHPeer, cmd: protocol.Command,
                         msg: protocol._DecodedMsgType) -> None:
        if isinstance(cmd, eth.BlockHeaders):
            msg = cast(List[BlockHeader], msg)
            self.logger.debug(
                "Got BlockHeaders from %d to %d", msg[0].block_number, msg[-1].block_number)
            self._new_headers.put_nowait(msg)
        elif isinstance(cmd, eth.BlockBodies):
            msg = cast(List[eth.BlockBody], msg)
            self.logger.debug("Got %d BlockBodies", len(msg))
            for body in msg:
                tx_root, trie_dict_data = make_trie_root_and_nodes(body.transactions)
                await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
                # TODO: Add transactions to canonical chain; blocked by
                # https://github.com/ethereum/py-evm/issues/337
                uncles_hash = await self.chaindb.coro_persist_uncles(body.uncles)
                self._pending_bodies.pop((tx_root, uncles_hash), None)
        elif isinstance(cmd, eth.Receipts):
            msg = cast(List[List[eth.Receipt]], msg)
            self.logger.debug("Got Receipts for %d blocks", len(msg))
            for block_receipts in msg:
                receipt_root, trie_dict_data = make_trie_root_and_nodes(block_receipts)
                await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
                self._pending_receipts.pop(receipt_root, None)
        elif isinstance(cmd, eth.NewBlock):
            msg = cast(Dict[str, Any], msg)
            header = msg['block'][0]
            actual_head = header.parent_hash
            actual_td = msg['total_difficulty'] - header.difficulty
            if actual_td > peer.head_td:
                peer.head_hash = actual_head
                peer.head_td = actual_td
                self._sync_requests.put_nowait(peer)
        elif isinstance(cmd, eth.Transactions):
            # TODO: Figure out what to do with those.
            pass
        elif isinstance(cmd, eth.NewBlockHashes):
            # TODO: Figure out what to do with those.
            pass
        else:
            # TODO: There are other msg types we'll want to handle here, but for now just log them
            # as a warning so we don't forget about it.
            self.logger.warn("Got unexpected msg: %s (%s)", cmd, msg)


def _test() -> None:
    import argparse
    import signal
    from p2p import ecies
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
    from evm.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB, LocalGethPeerPool
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger('p2p.chain.ChainSyncer').setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-local-geth', action="store_true")
    args = parser.parse_args()

    chaindb = FakeAsyncChainDB(LevelDB(args.db))
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    if args.local_geth:
        peer_pool = LocalGethPeerPool(
            ETHPeer, chaindb, RopstenChain.network_id, ecies.generate_privkey())
    else:
        peer_pool = PeerPool(ETHPeer, chaindb, RopstenChain.network_id, ecies.generate_privkey())
    asyncio.ensure_future(peer_pool.run())

    downloader = ChainSyncer(chaindb, peer_pool)

    async def run():
        # downloader.run() will run in a loop until the SIGINT/SIGTERM handler triggers its cancel
        # token, at which point it returns and we stop the pool and downloader.
        await downloader.run()
        await peer_pool.stop()
        await downloader.stop()

    loop = asyncio.get_event_loop()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, downloader.cancel_token.trigger)
    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
