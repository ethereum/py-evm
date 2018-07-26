import asyncio
import collections
import logging
import time
from typing import (
    Any,
    cast,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    TYPE_CHECKING,
    Union,
)

import rlp

from trie.sync import (
    HexaryTrieSync,
    SyncRequest,
)
from trie.exceptions import SyncRequestAlreadyProcessed

from eth_utils import (
    encode_hex,
)

from eth_hash.auto import keccak

from eth_typing import (
    Hash32
)

from cancel_token import CancelToken, OperationCancelled

from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from eth.db.backends.base import BaseDB
from eth.rlp.accounts import Account

from p2p import eth
from p2p import protocol
from p2p.chain import PeerRequestHandler
from p2p.exceptions import NoEligiblePeers
from p2p.peer import BasePeer, ETHPeer, HeaderRequest, PeerPool, PeerSubscriber
from p2p.service import BaseService
from p2p.utils import get_asyncio_executor, Timer


if TYPE_CHECKING:
    from trinity.db.chain import AsyncChainDB  # noqa: F401


class StateDownloader(BaseService, PeerSubscriber):
    _total_processed_nodes = 0
    _report_interval = 10  # Number of seconds between progress reports.
    _reply_timeout = 20  # seconds
    _timer = Timer(auto_start=False)
    _total_timeouts = 0

    def __init__(self,
                 chaindb: 'AsyncChainDB',
                 account_db: BaseDB,
                 root_hash: bytes,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chaindb = chaindb
        self.peer_pool = peer_pool
        self.root_hash = root_hash
        self.scheduler = StateSync(root_hash, account_db)
        self._handler = PeerRequestHandler(self.chaindb, self.logger, self.cancel_token)
        self._requested_nodes: Dict[ETHPeer, Tuple[float, List[Hash32]]] = {}
        self._peer_missing_nodes: Dict[ETHPeer, List[Hash32]] = collections.defaultdict(list)
        self._executor = get_asyncio_executor()

    @property
    def msg_queue_maxsize(self) -> int:
        # This is a rather arbitrary value, but when the sync is operating normally we never see
        # the msg queue grow past a few hundred items, so this should be a reasonable limit for
        # now.
        return 2000

    def deregister_peer(self, peer: BasePeer) -> None:
        # Use .pop() with a default value as it's possible we never requested anything to this
        # peer or it had all the trie nodes we requested, so there'd be no entry in
        # self._peer_missing_nodes for it.
        self._peer_missing_nodes.pop(cast(ETHPeer, peer), None)

    async def get_peer_for_request(self, node_keys: Set[Hash32]) -> ETHPeer:
        """Return an idle peer that may have any of the trie nodes in node_keys."""
        async for peer in self.peer_pool:
            peer = cast(ETHPeer, peer)
            if peer in self._requested_nodes:
                self.logger.trace("%s is not idle, skipping it", peer)
                continue
            if node_keys.difference(self._peer_missing_nodes[peer]):
                return peer
            else:
                self.logger.trace("%s doesn't have the nodes we want, skipping it", peer)
        raise NoEligiblePeers()

    async def _handle_msg_loop(self) -> None:
        while self.is_running:
            try:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
            except OperationCancelled:
                break

            # Run self._handle_msg() with ensure_future() instead of awaiting for it so that we
            # can keep consuming msgs while _handle_msg() performs cpu-intensive tasks in separate
            # processes.
            peer = cast(ETHPeer, peer)
            asyncio.ensure_future(self._handle_msg(peer, cmd, msg))

    async def _process_nodes(self, nodes: Iterable[Tuple[Hash32, bytes]]) -> None:
        for idx, (node_key, node) in enumerate(nodes):
            self._total_processed_nodes += 1
            try:
                self.scheduler.process([(node_key, node)])
            except SyncRequestAlreadyProcessed:
                # This means we received a node more than once, which can happen when we
                # retry after a timeout.
                pass
            if idx % 10 == 0:
                # XXX: This is a quick workaround for
                # https://github.com/ethereum/py-evm/issues/1074, which will be replaced soon
                # with a proper fix.
                await self.wait(asyncio.sleep(0))

    async def _handle_msg(
            self, peer: ETHPeer, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        # Throughout the whole state sync our chain head is fixed, so it makes sense to ignore
        # messages related to new blocks/transactions, but we must handle requests for data from
        # other peers or else they will disconnect from us.
        ignored_commands = (eth.Transactions, eth.NewBlock, eth.NewBlockHashes)
        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, eth.NodeData):
            msg = cast(List[bytes], msg)
            if peer not in self._requested_nodes:
                # This is probably a batch that we retried after a timeout and ended up receiving
                # more than once, so ignore but log as an INFO just in case.
                self.logger.info(
                    "Got %d NodeData entries from %s that were not expected, ignoring them",
                    len(msg), peer)
                return

            self.logger.debug("Got %d NodeData entries from %s", len(msg), peer)
            _, requested_node_keys = self._requested_nodes.pop(peer)

            loop = asyncio.get_event_loop()
            node_keys = await loop.run_in_executor(self._executor, list, map(keccak, msg))

            missing = set(requested_node_keys).difference(node_keys)
            self._peer_missing_nodes[peer].extend(missing)
            if missing:
                await self.request_nodes(missing)

            await self._process_nodes(zip(node_keys, msg))
        elif isinstance(cmd, eth.GetBlockHeaders):
            query = cast(Dict[Any, Union[bool, int]], msg)
            request = HeaderRequest(
                query['block_number_or_hash'],
                query['max_headers'],
                query['skip'],
                cast(bool, query['reverse']),
            )
            await self._handle_get_block_headers(peer, request)
        elif isinstance(cmd, eth.GetBlockBodies):
            # Only serve up to eth.MAX_BODIES_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth.MAX_BODIES_FETCH]
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, eth.GetReceipts):
            # Only serve up to eth.MAX_RECEIPTS_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth.MAX_RECEIPTS_FETCH]
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, eth.GetNodeData):
            # Only serve up to eth.MAX_STATE_FETCH items in every request.
            node_hashes = cast(List[Hash32], msg)[:eth.MAX_STATE_FETCH]
            await self._handler.handle_get_node_data(peer, node_hashes)
        else:
            self.logger.warn("%s not handled during StateSync, must be implemented", cmd)

    async def _handle_get_block_headers(self, peer: ETHPeer, request: HeaderRequest) -> None:
        headers = await self._handler.lookup_headers(request)
        peer.sub_proto.send_block_headers(headers)

    async def _cleanup(self) -> None:
        # We don't need to cancel() anything, but we yield control just so that the coroutines we
        # run in the background notice the cancel token has been triggered and return.
        await asyncio.sleep(0)

    async def request_nodes(self, node_keys: Iterable[Hash32]) -> None:
        not_yet_requested = set(node_keys)
        while not_yet_requested:
            try:
                peer = await self.get_peer_for_request(not_yet_requested)
            except NoEligiblePeers:
                self.logger.debug(
                    "No idle peers have any of the trie nodes we want, sleeping a bit")
                await self.wait(asyncio.sleep(0.2))
                continue

            candidates = list(not_yet_requested.difference(self._peer_missing_nodes[peer]))
            batch = candidates[:eth.MAX_STATE_FETCH]
            not_yet_requested = not_yet_requested.difference(batch)
            self._requested_nodes[peer] = (time.time(), batch)
            self.logger.debug("Requesting %d trie nodes to %s", len(batch), peer)
            peer.sub_proto.send_get_node_data(batch)

    async def _periodically_retry_timedout(self) -> None:
        while self.is_running:
            now = time.time()
            oldest_request_time = now
            timed_out = []
            # Iterate over a copy of our dict's items as we're going to mutate it.
            for peer, (req_time, node_keys) in list(self._requested_nodes.items()):
                if now - req_time > self._reply_timeout:
                    self.logger.debug(
                        "Timed out waiting for %d nodes from %s", len(node_keys), peer)
                    timed_out.extend(node_keys)
                    self._requested_nodes.pop(peer)
                elif req_time < oldest_request_time:
                    oldest_request_time = req_time
            if timed_out:
                self.logger.debug("Re-requesting %d trie nodes", len(timed_out))
                self._total_timeouts += len(timed_out)
                try:
                    await self.request_nodes(timed_out)
                except OperationCancelled:
                    break

            # Finally, sleep until the time our oldest request is scheduled to timeout.
            now = time.time()
            sleep_duration = (oldest_request_time + self._reply_timeout) - now
            try:
                await self.wait(asyncio.sleep(sleep_duration))
            except OperationCancelled:
                break

    async def _run(self) -> None:
        """Fetch all trie nodes starting from self.root_hash, and store them in self.db.

        Raises OperationCancelled if we're interrupted before that is completed.
        """
        self._timer.start()
        self.logger.info("Starting state sync for root hash %s", encode_hex(self.root_hash))
        asyncio.ensure_future(self._handle_msg_loop())
        asyncio.ensure_future(self._periodically_report_progress())
        asyncio.ensure_future(self._periodically_retry_timedout())
        with self.subscribe(self.peer_pool):
            while self.scheduler.has_pending_requests:
                # This ensures we yield control and give _handle_msg() a chance to process any nodes
                # we may have received already, also ensuring we exit when our cancel token is
                # triggered.
                await self.wait(asyncio.sleep(0))

                requests = self.scheduler.next_batch(eth.MAX_STATE_FETCH)
                if not requests:
                    # Although we frequently yield control above, to let our msg handler process
                    # received nodes (scheduling new requests), there may be cases when the
                    # pending nodes take a while to arrive thus causing the scheduler to run out
                    # of new requests for a while.
                    self.logger.debug("Scheduler queue is empty, sleeping a bit")
                    await self.wait(asyncio.sleep(0.5))
                    continue

                await self.request_nodes([request.node_key for request in requests])

        self.logger.info("Finished state sync with root hash %s", encode_hex(self.root_hash))

    async def _periodically_report_progress(self) -> None:
        while self.is_running:
            requested_nodes = sum(
                len(node_keys) for _, node_keys in self._requested_nodes.values())
            self.logger.info("====== State sync progress ========")
            self.logger.info("Nodes processed: %d", self._total_processed_nodes)
            self.logger.info("Nodes processed per second (average): %d",
                             self._total_processed_nodes / self._timer.elapsed)
            self.logger.info("Nodes committed to DB: %d", self.scheduler.committed_nodes)
            self.logger.info("Nodes requested but not received yet: %d", requested_nodes)
            self.logger.info(
                "Nodes scheduled but not requested yet: %d", len(self.scheduler.requests))
            self.logger.info("Total nodes timed out: %d", self._total_timeouts)
            try:
                await self.wait(asyncio.sleep(self._report_interval))
            except OperationCancelled:
                break


class StateSync(HexaryTrieSync):

    def __init__(self, root_hash: Hash32, db: BaseDB) -> None:
        super().__init__(root_hash, db, logging.getLogger("p2p.state.StateSync"))

    def leaf_callback(self, data: bytes, parent: SyncRequest) -> None:
        # TODO: Need to figure out why geth uses 64 as the depth here, and then document it.
        depth = 64
        account = rlp.decode(data, sedes=Account)
        if account.storage_root != BLANK_ROOT_HASH:
            self.schedule(account.storage_root, parent, depth, leaf_callback=None)
        if account.code_hash != EMPTY_SHA3:
            self.schedule(account.code_hash, parent, depth, leaf_callback=None, is_raw=True)


def _test() -> None:
    import argparse
    import signal
    from p2p import ecies
    from p2p.peer import DEFAULT_PREFERRED_NODES
    from eth.chains.ropsten import RopstenChain, ROPSTEN_VM_CONFIGURATION
    from eth.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB, connect_to_peers_loop
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-debug', action="store_true")
    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.state.StateDownloader').setLevel(log_level)

    db = LevelDB(args.db)
    chaindb = FakeAsyncChainDB(db)
    network_id = RopstenChain.network_id
    nodes = DEFAULT_PREFERRED_NODES[network_id]
    peer_pool = PeerPool(
        ETHPeer, chaindb, network_id, ecies.generate_privkey(), ROPSTEN_VM_CONFIGURATION)
    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, nodes))

    head = chaindb.get_canonical_head()
    downloader = StateDownloader(chaindb, db, head.state_root, peer_pool)
    loop = asyncio.get_event_loop()

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await peer_pool.cancel()
        await downloader.cancel()
        loop.stop()

    async def run() -> None:
        await downloader.run()
        downloader.logger.info("run() finished, exiting")
        sigint_received.set()

    # loop.set_debug(True)
    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(run())
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    # Use the snippet below to get profile stats and print the top 50 functions by cumulative time
    # used.
    # import cProfile, pstats  # noqa
    # cProfile.run('_test()', 'stats')
    # pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    _test()
