import asyncio
import logging
import math
import operator
import time
from typing import (  # noqa: F401
    Any, Awaitable, Callable, cast, Dict, Generator, List, Set, Tuple, Union)

from cytoolz.itertoolz import partition_all, unique

from evm.constants import BLANK_ROOT_HASH, EMPTY_UNCLE_HASH
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

    def __init__(self,
                 chaindb: AsyncChainDB,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        self.chaindb = chaindb
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self.cancel_token = CancelToken('ChainSyncer')
        if token is not None:
            self.cancel_token = self.cancel_token.chain(token)
        self._running_peers = set()  # type: Set[ETHPeer]
        self._syncing = False
        self._sync_complete = asyncio.Event()
        self._sync_requests = asyncio.Queue()  # type: asyncio.Queue[ETHPeer]
        self._new_headers = asyncio.Queue()  # type: asyncio.Queue[List[BlockHeader]]
        self._downloaded_receipts = asyncio.Queue()  # type: asyncio.Queue[List[bytes]]
        self._downloaded_bodies = asyncio.Queue()  # type: asyncio.Queue[List[Tuple[bytes, bytes]]]

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
            peer_or_finished = await wait_with_token(
                self._sync_requests.get(), self._sync_complete.wait(),
                token=self.cancel_token)

            if self._sync_complete.is_set():
                return

            # Since self._sync_complete is not set, peer_or_finished can only be a ETHPeer
            # instance.
            asyncio.ensure_future(self.sync(peer_or_finished))

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
        except OperationCancelled:
            pass
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

        self.logger.info("Starting sync with %s", peer)
        # FIXME: Fetch a batch of headers, in reverse order, starting from our current head, and
        # find the common ancestor between our chain and the peer's.
        start_at = max(0, head.block_number - eth.MAX_HEADERS_FETCH)
        while True:
            self.logger.info("Fetching chain segment starting at #%d", start_at)
            peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)
            try:
                headers = await wait_with_token(
                    self._new_headers.get(), peer.wait_until_finished(),
                    token=self.cancel_token,
                    timeout=self._reply_timeout)
            except TimeoutError:
                self.logger.warn("Timeout waiting for header batch from %s, aborting sync", peer)
                await peer.stop()
                break

            if peer.is_finished():
                self.logger.info("%s disconnected, aborting sync", peer)
                break

            self.logger.info("Got headers segment starting at #%d", start_at)

            # TODO: Process headers for consistency.

            await self._download_block_parts(
                [header for header in headers if not _is_body_empty(header)],
                self.request_bodies,
                self._downloaded_bodies,
                _body_key,
                'body')

            self.logger.info("Got block bodies for chain segment starting at #%d", start_at)

            missing_receipts = [header for header in headers if not _is_receipts_empty(header)]
            # Post-Byzantium blocks may have identical receipt roots (e.g. when they have the same
            # number of transactions and all succeed/failed: ropsten blocks 2503212 and 2503284),
            # so we do this to avoid requesting the same receipts multiple times.
            missing_receipts = list(unique(missing_receipts, key=_receipts_key))
            await self._download_block_parts(
                missing_receipts,
                self.request_receipts,
                self._downloaded_receipts,
                _receipts_key,
                'receipt')

            self.logger.info("Got block receipts for chain segment starting at #%d", start_at)

            for header in headers:
                await self.chaindb.coro_persist_header(header)
                start_at = header.block_number + 1

            self.logger.info("Imported chain segment, new head: #%d", start_at - 1)
            head = await self.chaindb.coro_get_canonical_head()
            if head.hash == peer.head_hash:
                self.logger.info("Chain sync with %s completed", peer)
                self._sync_complete.set()
                break

    async def _download_block_parts(
            self,
            headers: List[BlockHeader],
            request_func: Callable[[List[BlockHeader]], int],
            download_queue: 'Union[asyncio.Queue[List[bytes]], asyncio.Queue[List[Tuple[bytes, bytes]]]]',  # noqa: E501
            key_func: Callable[[BlockHeader], Union[bytes, Tuple[bytes, bytes]]],
            part_name: str) -> None:
        missing = headers.copy()
        # The ETH protocol doesn't guarantee that we'll get all body parts requested, so we need
        # to keep track of the number of pending replies and missing items to decide when to retry
        # them. See request_receipts() for more info.
        pending_replies = request_func(missing)
        while missing:
            if pending_replies == 0:
                pending_replies = request_func(missing)

            try:
                downloaded = await wait_with_token(
                    download_queue.get(),
                    token=self.cancel_token,
                    timeout=self._reply_timeout)
            except TimeoutError:
                pending_replies = request_func(missing)
                continue

            pending_replies -= 1
            unexpected = set(downloaded).difference(
                [key_func(header) for header in missing])
            for item in unexpected:
                self.logger.warn("Got unexpected %s: %s", part_name, unexpected)
            missing = [
                header for header in missing
                if key_func(header) not in downloaded]

    def _request_block_parts(
            self,
            headers: List[BlockHeader],
            request_func: Callable[[ETHPeer, List[BlockHeader]], None]) -> int:
        length = math.ceil(len(headers) / len(self.peer_pool.peers))
        batches = list(partition_all(length, headers))
        for peer, batch in zip(self.peer_pool.peers, batches):
            request_func(cast(ETHPeer, peer), batch)
        return len(batches)

    def _send_get_block_bodies(self, peer: ETHPeer, headers: List[BlockHeader]) -> None:
        self.logger.debug("Requesting %d block bodies to %s", len(headers), peer)
        peer.sub_proto.send_get_block_bodies([header.hash for header in headers])

    def _send_get_receipts(self, peer: ETHPeer, headers: List[BlockHeader]) -> None:
        self.logger.debug("Requesting %d block receipts to %s", len(headers), peer)
        peer.sub_proto.send_get_receipts([header.hash for header in headers])

    def request_bodies(self, headers: List[BlockHeader]) -> int:
        """Ask our peers for bodies for the given headers.

        See request_receipts() for details of how this is done.
        """
        return self._request_block_parts(headers, self._send_get_block_bodies)

    def request_receipts(self, headers: List[BlockHeader]) -> int:
        """Ask our peers for receipts for the given headers.

        We partition the given list of headers in batches and request each to one of our connected
        peers. This is done because geth enforces a byte-size cap when replying to a GetReceipts
        msg, and we then need to re-request the items that didn't fit, so by splitting the
        requests across all our peers we reduce the likelyhood of having to make multiple
        serialized requests to ask for missing items (which happens quite frequently in practice).

        Returns the number of requests made.
        """
        return self._request_block_parts(headers, self._send_get_receipts)

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
        if isinstance(cmd, eth.BlockHeaders):
            msg = cast(List[BlockHeader], msg)
            self.logger.debug(
                "Got BlockHeaders from %d to %d", msg[0].block_number, msg[-1].block_number)
            self._new_headers.put_nowait(msg)
        elif isinstance(cmd, eth.BlockBodies):
            await self._handle_block_bodies(peer, cast(List[eth.BlockBody], msg))
        elif isinstance(cmd, eth.Receipts):
            await self._handle_block_receipts(peer, cast(List[List[eth.Receipt]], msg))
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

    async def _handle_block_receipts(
            self, peer: ETHPeer, receipts: List[List[eth.Receipt]]) -> None:
        self.logger.debug("Got Receipts for %d blocks from %s", len(receipts), peer)
        loop = asyncio.get_event_loop()
        iterator = map(make_trie_root_and_nodes, receipts)
        receipts_tries = await wait_with_token(
            loop.run_in_executor(None, list, iterator),
            token=self.cancel_token)
        for receipt_root, trie_dict_data in receipts_tries:
            await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
        receipt_roots = [receipt_root for receipt_root, _ in receipts_tries]
        self._downloaded_receipts.put_nowait(receipt_roots)

    async def _handle_block_bodies(self, peer: ETHPeer, bodies: List[eth.BlockBody]) -> None:
        self.logger.debug("Got Bodies for %d blocks from %s", len(bodies), peer)
        loop = asyncio.get_event_loop()
        iterator = map(make_trie_root_and_nodes, [body.transactions for body in bodies])
        transactions_tries = await wait_with_token(
            loop.run_in_executor(None, list, iterator),
            token=self.cancel_token)
        body_keys = []
        for (body, (tx_root, trie_dict_data)) in zip(bodies, transactions_tries):
            await self.chaindb.coro_persist_trie_data_dict(trie_dict_data)
            uncles_hash = await self.chaindb.coro_persist_uncles(body.uncles)
            body_keys.append((tx_root, uncles_hash))
        self._downloaded_bodies.put_nowait(body_keys)


def _body_key(header: BlockHeader) -> Tuple[bytes, bytes]:
    """Return the unique key of the body for the given header.

    i.e. a two-tuple with the transaction root and uncles hash.
    """
    return cast(Tuple[bytes, bytes], (header.transaction_root, header.uncles_hash))


def _receipts_key(header: BlockHeader) -> bytes:
    """Return the unique key of the list of receipts for the given header.

    i.e. the header's receipt root.
    """
    return header.receipt_root


def _is_body_empty(header: BlockHeader) -> bool:
    return header.transaction_root == BLANK_ROOT_HASH and header.uncles_hash == EMPTY_UNCLE_HASH


def _is_receipts_empty(header: BlockHeader) -> bool:
    return header.receipt_root == BLANK_ROOT_HASH


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
        try:
            await downloader.run()
        except OperationCancelled:
            pass
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
