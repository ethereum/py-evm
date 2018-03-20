import asyncio
import logging
import operator
import secrets
import time
from typing import Any, Awaitable, Callable, cast, Dict, Generator, List, Set, Tuple  # noqa: F401

from cytoolz.itertoolz import unique

from eth_utils import (
    encode_hex,
    to_list,
)

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
    # TODO: Instead of a fixed timeout, we should use a variable one that gets adjusted based on
    # the round-trip times from our download requests.
    _reply_timeout = 60

    def __init__(self, chaindb: AsyncChainDB, peer_pool: PeerPool) -> None:
        self.chaindb = chaindb
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self.cancel_token = CancelToken('ChainSyncer')
        self._running_peers = set()  # type: Set[ETHPeer]
        self._peers_with_pending_requests = set()  # type: Set[ETHPeer]
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

            pending_msgs = peer.sub_proto_msg_queue.qsize()
            if pending_msgs:
                self.logger.debug(
                    "Read %s msg from %s's queue; %d msgs pending", cmd, peer, pending_msgs)

            # Our handle_msg() method runs cpu-intensive tasks in sub-processes so that the main
            # loop can keep processing msgs, and that's why we use ensure_future() instead of
            # awaiting for it to finish here.
            asyncio.ensure_future(self.handle_msg(peer, cmd, msg))

    async def handle_msg(self, peer: ETHPeer, cmd: protocol.Command,
                         msg: protocol._DecodedMsgType) -> None:
        try:
            await self._handle_msg(peer, cmd, msg)
        except OperationCancelled:
            # Silently swallow OperationCancelled exceptions because we run unsupervised (i.e.
            # with ensure_future()). Our caller will also get an OperationCancelled anyway, and
            # there it will be handled.
            pass
        except Exception:
            self.logger.exception("Unexpected error when processing msg from %s", peer)

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
            self.logger.warn(
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
            self.logger.info(
                "Head TD (%d) announced by %s not higher than ours (%d), not syncing",
                peer.head_td, peer, head_td)
            return

        # FIXME: Fetch a batch of headers, in reverse order, starting from our current head, and
        # find the common ancestor between our chain and the peer's.
        start_at = max(0, head.block_number - eth.MAX_HEADERS_FETCH)
        self.logger.debug("Asking %s for header batch starting at %d", peer, start_at)
        peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)
        while True:
            # TODO: Consider stalling header fetching if there are more than X blocks/receipts
            # pending, to avoid timeouts caused by us not being able to process (decode/store)
            # blocks/receipts fast enough.
            try:
                headers = await wait_with_token(
                    self._new_headers.get(), peer.wait_until_finished(),
                    token=self.cancel_token,
                    timeout=self._reply_timeout)
            except OperationCancelled:
                break
            except TimeoutError:
                self.logger.warn("Timeout waiting for header batch from %s, aborting sync", peer)
                await peer.stop()
                break

            if peer.is_finished():
                self.logger.info("%s disconnected, aborting sync", peer)
                break

            # TODO: Process headers for consistency.
            for header in headers:
                await self.chaindb.coro_persist_header(header)
                start_at = header.block_number + 1

            self._body_requests.put_nowait(headers)
            self._receipt_requests.put_nowait(headers)

            self.logger.debug("Asking %s for header batch starting at %d", peer, start_at)
            # TODO: Instead of requesting sequential batches from a single peer, request a header
            # skeleton and make concurrent requests, using as many peers as possible, to fill the
            # skeleton.
            peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)

    async def _downloader(self,
                          queue: 'asyncio.Queue[List[BlockHeader]]',
                          filter_func: Callable[[List[BlockHeader]], List[BlockHeader]],
                          request_func: Callable[[List[BlockHeader]], Awaitable[None]],
                          pending: Dict[Any, Tuple[BlockHeader, float]],
                          batch_size: int,
                          part_name: str) -> None:
        batch = []  # type: List[BlockHeader]
        while True:
            try:
                headers = await wait_with_token(
                    queue.get(),
                    token=self.cancel_token,
                    # Use a shorter timeout here because this only causes the actual retry
                    # coroutine (self._retry_timedout) to go through the pending ones and retry
                    # any items that are pending for more than self._reply_timeout seconds.
                    timeout=self._reply_timeout / 2)
                batch.extend(headers)
            except TimeoutError:
                # We use a timeout above to make sure we periodically retry timedout items
                # even when there's no new items coming through.
                pass
            except OperationCancelled:
                return
            else:
                # Re-apply the filter function on all items because one of the things it may do is
                # drop items that have the same receipt_root.
                batch = filter_func(batch)
                if len(batch) >= batch_size:
                    await request_func(batch[:batch_size])
                    batch = batch[batch_size:]

            await self._retry_timedout(request_func, pending, batch_size, part_name)

    async def _retry_timedout(self,
                              request_func: Callable[[List[BlockHeader]], Awaitable[None]],
                              pending: Dict[Any, Tuple[BlockHeader, float]],
                              batch_size: int,
                              part_name: str) -> None:
        now = time.time()
        timed_out = [
            header
            for header, req_time
            in pending.values()
            if now - req_time > self._reply_timeout
        ]
        while timed_out:
            self.logger.warn(
                "Re-requesting %d timed out %s out of %d pending ones",
                len(timed_out), part_name, len(pending))
            await request_func(timed_out[:batch_size])
            timed_out = timed_out[batch_size:]

    async def body_downloader(self) -> None:
        await self._downloader(
            self._body_requests,
            self._skip_empty_bodies,
            self.request_bodies,
            self._pending_bodies,
            eth.MAX_BODIES_FETCH,
            'bodies')

    async def receipt_downloader(self) -> None:
        await self._downloader(
            self._receipt_requests,
            self._skip_empty_and_duplicated_receipts,
            self.request_receipts,
            self._pending_receipts,
            eth.MAX_RECEIPTS_FETCH,
            'receipts')

    @to_list
    def _skip_empty_bodies(self, headers: List[BlockHeader]) -> Generator[BlockHeader, None, None]:
        for header in headers:
            if (header.transaction_root != self.chaindb.empty_root_hash or
                    header.uncles_hash != EMPTY_UNCLE_HASH):
                yield header

    async def request_bodies(self, headers: List[BlockHeader]) -> None:
        peer = await self.get_idle_peer()
        peer.sub_proto.send_get_block_bodies([header.hash for header in headers])
        self._peers_with_pending_requests.add(peer)
        self.logger.debug("Requesting %d block bodies to %s", len(headers), peer)
        now = time.time()
        for header in headers:
            key = (header.transaction_root, header.uncles_hash)
            self._pending_bodies[key] = (header, now)

    @to_list
    def _skip_empty_and_duplicated_receipts(
            self, headers: List[BlockHeader]) -> Generator[BlockHeader, None, None]:
        # Post-Byzantium blocks may have identical receipt roots (e.g. when they have the same
        # number of transactions and all succeed/failed: ropsten blocks 2503212 and 2503284), so
        # we have an extra check here to avoid requesting those receipts multiple times.
        headers = list(unique(headers, key=operator.attrgetter('receipt_root')))
        for header in headers:
            if (header.receipt_root != self.chaindb.empty_root_hash and
                    header.receipt_root not in self._pending_receipts):
                yield header

    async def request_receipts(self, headers: List[BlockHeader]) -> None:
        peer = await self.get_idle_peer()
        peer.sub_proto.send_get_receipts([header.hash for header in headers])
        self._peers_with_pending_requests.add(peer)
        self.logger.debug("Requesting %d block receipts to %s", len(headers), peer)
        now = time.time()
        for header in headers:
            self._pending_receipts[header.receipt_root] = (header, now)

    async def get_idle_peer(self) -> ETHPeer:
        """Return a random peer which we're not already expecting a response from."""
        while True:
            idle_peers = [
                peer
                for peer in self.peer_pool.peers
                if peer not in self._peers_with_pending_requests
            ]
            if idle_peers:
                return cast(ETHPeer, secrets.choice(idle_peers))
            else:
                self.logger.debug("No idle peers availabe, sleeping a bit")
                await asyncio.sleep(0.2)

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

    async def _handle_msg(self, peer: ETHPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        loop = asyncio.get_event_loop()
        if isinstance(cmd, eth.BlockHeaders):
            msg = cast(List[BlockHeader], msg)
            self.logger.debug(
                "Got BlockHeaders from %d to %d", msg[0].block_number, msg[-1].block_number)
            self._new_headers.put_nowait(msg)
        elif isinstance(cmd, eth.BlockBodies):
            self._peers_with_pending_requests.remove(peer)
            msg = cast(List[eth.BlockBody], msg)
            self.logger.debug("Got %d BlockBodies from %s", len(msg), peer)
            iterator = map(make_trie_root_and_nodes, [body.transactions for body in msg])
            transactions_tries = await wait_with_token(
                loop.run_in_executor(None, list, iterator),
                token=self.cancel_token)
            for i in range(len(msg)):
                body = msg[i]
                tx_root, trie_dict_data = transactions_tries[i]
                await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
                # TODO: Add transactions to canonical chain; blocked by
                # https://github.com/ethereum/py-evm/issues/337
                uncles_hash = await self.chaindb.coro_persist_uncles(body.uncles)
                self._pending_bodies.pop((tx_root, uncles_hash), None)
        elif isinstance(cmd, eth.Receipts):
            self._peers_with_pending_requests.remove(peer)
            msg = cast(List[List[eth.Receipt]], msg)
            self.logger.debug("Got Receipts for %d blocks from %s", len(msg), peer)
            iterator = map(make_trie_root_and_nodes, msg)
            receipts_tries = await wait_with_token(
                loop.run_in_executor(None, list, iterator),
                token=self.cancel_token)
            for receipt_root, trie_dict_data in receipts_tries:
                if receipt_root not in self._pending_receipts:
                    self.logger.warning(
                        "Got unexpected receipt root: %s",
                        encode_hex(receipt_root),
                    )
                    continue
                await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
                self._pending_receipts.pop(receipt_root)
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
    from concurrent.futures import ProcessPoolExecutor
    import signal
    from p2p import ecies
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
    from evm.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB, LocalGethPeerPool

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-local-geth', action="store_true")
    parser.add_argument('-debug', action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.chain.ChainSyncer').setLevel(log_level)

    loop = asyncio.get_event_loop()
    # Use a ProcessPoolExecutor as the default because the tasks we want to offload from the main
    # thread are cpu intensive.
    loop.set_default_executor(ProcessPoolExecutor())
    chaindb = FakeAsyncChainDB(LevelDB(args.db))
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    privkey = ecies.generate_privkey()
    if args.local_geth:
        peer_pool = LocalGethPeerPool(ETHPeer, chaindb, RopstenChain.network_id, privkey)
    else:
        from p2p.peer import HardCodedNodesPeerPool
        min_peers = 5
        peer_pool = HardCodedNodesPeerPool(
            ETHPeer, chaindb, RopstenChain.network_id, privkey, min_peers)

    asyncio.ensure_future(peer_pool.run())
    downloader = ChainSyncer(chaindb, peer_pool)

    async def run():
        # downloader.run() will run in a loop until the SIGINT/SIGTERM handler triggers its cancel
        # token, at which point it returns and we stop the pool and downloader.
        await downloader.run()
        await peer_pool.stop()
        await downloader.stop()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, downloader.cancel_token.trigger)
    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    # Use the snippet below to get profile stats and print the top 50 functions by cumulative time
    # used.
    # import cProfile, pstats  # noqa
    # cProfile.run('_test()', 'stats')
    # pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    _test()
