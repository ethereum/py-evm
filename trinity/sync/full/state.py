import asyncio
import collections
import itertools
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
    Type,
    Union,
)

import cytoolz

import rlp

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
from eth.rlp.accounts import Account
from eth.utils.logging import TraceLogger

from p2p.service import BaseService
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from p2p.exceptions import NoEligiblePeers, NoIdlePeers
from p2p.peer import BasePeer, PeerPool, PeerSubscriber
from p2p.executor import get_asyncio_executor

from trinity.db.base import AsyncBaseDB
from trinity.db.chain import AsyncChainDB
from trinity.exceptions import SyncRequestAlreadyProcessed
from trinity.p2p.handlers import PeerRequestHandler
from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.requests import HeaderRequest
from trinity.protocol.eth import commands
from trinity.protocol.eth import (
    constants as eth_constants,
)
from trinity.sync.full.hexary_trie import (
    HexaryTrieSync,
    SyncRequest,
)

from trinity.utils.timer import Timer


class StateDownloader(BaseService, PeerSubscriber):
    _total_processed_nodes = 0
    _report_interval = 10  # Number of seconds between progress reports.
    _reply_timeout = 20  # seconds
    _timer = Timer(auto_start=False)
    _total_timeouts = 0

    def __init__(self,
                 chaindb: AsyncChainDB,
                 account_db: AsyncBaseDB,
                 root_hash: bytes,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chaindb = chaindb
        self.peer_pool = peer_pool
        self.root_hash = root_hash
        self.scheduler = StateSync(root_hash, account_db, self.logger)
        self._handler = PeerRequestHandler(self.chaindb, self.logger, self.cancel_token)
        self.request_tracker = TrieNodeRequestTracker(self._reply_timeout, self.logger)
        self._peer_missing_nodes: Dict[ETHPeer, Set[Hash32]] = collections.defaultdict(set)
        self._executor = get_asyncio_executor()

    # Throughout the whole state sync our chain head is fixed, so it makes sense to ignore
    # messages related to new blocks/transactions, but we must handle requests for data from
    # other peers or else they will disconnect from us.
    subscription_msg_types: Set[Type[Command]] = {
        commands.NodeData,
        commands.GetBlockHeaders,
        commands.GetBlockBodies,
        commands.GetReceipts,
        commands.GetNodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        commands.Transactions,
        commands.NewBlock,
        commands.NewBlockHashes,
    }

    # This is a rather arbitrary value, but when the sync is operating normally we never see
    # the msg queue grow past a few hundred items, so this should be a reasonable limit for
    # now.
    msg_queue_maxsize: int = 2000

    def deregister_peer(self, peer: BasePeer) -> None:
        # Use .pop() with a default value as it's possible we never requested anything to this
        # peer or it had all the trie nodes we requested, so there'd be no entry in
        # self._peer_missing_nodes for it.
        self._peer_missing_nodes.pop(cast(ETHPeer, peer), None)

    async def get_peer_for_request(self, node_keys: Set[Hash32]) -> ETHPeer:
        """Return an idle peer that may have any of the trie nodes in node_keys.

        If none of our peers have any of the given node keys, raise NoEligiblePeers. If none of
        the peers which may have at least one of the given node keys is idle, raise NoIdlePeers.
        """
        has_eligible_peers = False
        async for peer in self.peer_pool:
            peer = cast(ETHPeer, peer)
            if self._peer_missing_nodes[peer].issuperset(node_keys):
                self.logger.trace("%s doesn't have any of the nodes we want, skipping it", peer)
                continue
            has_eligible_peers = True
            if peer in self.request_tracker.active_requests:
                self.logger.trace("%s is not idle, skipping it", peer)
                continue
            return peer

        if not has_eligible_peers:
            raise NoEligiblePeers()
        else:
            raise NoIdlePeers()

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
        for node_key, node in nodes:
            self._total_processed_nodes += 1
            try:
                await self.scheduler.process([(node_key, node)])
            except SyncRequestAlreadyProcessed:
                # This means we received a node more than once, which can happen when we
                # retry after a timeout.
                pass

    async def _handle_msg(
            self, peer: ETHPeer, cmd: Command, msg: _DecodedMsgType) -> None:
        # TODO: stop ignoring these once we have proper handling for these messages.
        ignored_commands = (commands.Transactions, commands.NewBlock, commands.NewBlockHashes)

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, commands.NodeData):
            msg = cast(List[bytes], msg)
            if peer not in self.request_tracker.active_requests:
                # This is probably a batch that we retried after a timeout and ended up receiving
                # more than once, so ignore but log as an INFO just in case.
                self.logger.info(
                    "Got %d NodeData entries from %s that were not expected, ignoring them",
                    len(msg), peer)
                return

            self.logger.debug("Got %d NodeData entries from %s", len(msg), peer)
            _, requested_node_keys = self.request_tracker.active_requests.pop(peer)

            loop = asyncio.get_event_loop()
            node_keys = await loop.run_in_executor(self._executor, list, map(keccak, msg))

            missing = set(requested_node_keys).difference(node_keys)
            self._peer_missing_nodes[peer].update(missing)
            if missing:
                await self.request_nodes(missing)

            await self._process_nodes(zip(node_keys, msg))
        elif isinstance(cmd, commands.GetBlockHeaders):
            query = cast(Dict[Any, Union[bool, int]], msg)
            request = HeaderRequest(
                query['block_number_or_hash'],
                query['max_headers'],
                query['skip'],
                cast(bool, query['reverse']),
            )
            await self._handle_get_block_headers(peer, request)
        elif isinstance(cmd, commands.GetBlockBodies):
            # Only serve up to MAX_BODIES_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_BODIES_FETCH]
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, commands.GetReceipts):
            # Only serve up to MAX_RECEIPTS_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_RECEIPTS_FETCH]
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, commands.GetNodeData):
            # Only serve up to MAX_STATE_FETCH items in every request.
            node_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_STATE_FETCH]
            await self._handler.handle_get_node_data(peer, node_hashes)
        else:
            self.logger.warn("%s not handled during StateSync, must be implemented", cmd)

    async def _handle_get_block_headers(self, peer: ETHPeer, request: HeaderRequest) -> None:
        headers = await self._handler.lookup_headers(request)
        peer.sub_proto.send_block_headers(headers)

    async def _cleanup(self) -> None:
        # We don't need to cancel() anything, but we yield control just so that the coroutines we
        # run in the background notice the cancel token has been triggered and return.
        # Also, don't use self.sleep() here as the cancel token will be triggered and that will
        # raise OperationCancelled.
        await asyncio.sleep(0)

    async def request_nodes(self, node_keys: Iterable[Hash32]) -> None:
        not_yet_requested = set(node_keys)
        while not_yet_requested:
            try:
                peer = await self.get_peer_for_request(not_yet_requested)
            except NoIdlePeers:
                self.logger.trace(
                    "No idle peers have any of the %d trie nodes we want, sleeping a bit",
                    len(not_yet_requested),
                )
                await self.sleep(0.2)
                continue
            except NoEligiblePeers:
                self.request_tracker.missing[time.time()] = list(not_yet_requested)
                self.logger.debug(
                    "No peers have any of the %d trie nodes in this batch, will retry later",
                    len(not_yet_requested),
                )
                # TODO: disconnect a peer if the pool is full
                return

            candidates = list(not_yet_requested.difference(self._peer_missing_nodes[peer]))
            batch = candidates[:eth_constants.MAX_STATE_FETCH]
            not_yet_requested = not_yet_requested.difference(batch)
            self.request_tracker.active_requests[peer] = (time.time(), batch)
            self.logger.debug("Requesting %d trie nodes to %s", len(batch), peer)
            peer.sub_proto.send_get_node_data(batch)

    async def _periodically_retry_timedout_and_missing(self) -> None:
        while self.is_running:
            timed_out = self.request_tracker.get_timed_out()
            if timed_out:
                self.logger.debug("Re-requesting %d timed out trie nodes", len(timed_out))
                self._total_timeouts += len(timed_out)
                try:
                    await self.request_nodes(timed_out)
                except OperationCancelled:
                    break

            retriable_missing = self.request_tracker.get_retriable_missing()
            if retriable_missing:
                self.logger.debug("Re-requesting %d missing trie nodes", len(timed_out))
                try:
                    await self.request_nodes(retriable_missing)
                except OperationCancelled:
                    break

            # Finally, sleep until the time either our oldest request is scheduled to timeout or
            # one of our missing batches is scheduled to be retried.
            next_timeout = self.request_tracker.get_next_timeout()
            try:
                await self.sleep(next_timeout - time.time())
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
        asyncio.ensure_future(self._periodically_retry_timedout_and_missing())
        with self.subscribe(self.peer_pool):
            while self.scheduler.has_pending_requests:
                # This ensures we yield control and give _handle_msg() a chance to process any nodes
                # we may have received already, also ensuring we exit when our cancel token is
                # triggered.
                await self.sleep(0)

                requests = self.scheduler.next_batch(eth_constants.MAX_STATE_FETCH)
                if not requests:
                    # Although we frequently yield control above, to let our msg handler process
                    # received nodes (scheduling new requests), there may be cases when the
                    # pending nodes take a while to arrive thus causing the scheduler to run out
                    # of new requests for a while.
                    self.logger.debug("Scheduler queue is empty, sleeping a bit")
                    await self.sleep(0.5)
                    continue

                await self.request_nodes([request.node_key for request in requests])

        self.logger.info("Finished state sync with root hash %s", encode_hex(self.root_hash))

    async def _periodically_report_progress(self) -> None:
        while self.is_running:
            requested_nodes = sum(
                len(node_keys) for _, node_keys in self.request_tracker.active_requests.values())
            msg = "processed=%d  " % self._total_processed_nodes
            msg += "tnps=%d  " % (self._total_processed_nodes / self._timer.elapsed)
            msg += "committed=%d  " % self.scheduler.committed_nodes
            msg += "requested=%d  " % requested_nodes
            msg += "scheduled=%d  " % len(self.scheduler.requests)
            msg += "timeouts=%d" % self._total_timeouts
            self.logger.info("State-Sync: %s", msg)
            try:
                await self.sleep(self._report_interval)
            except OperationCancelled:
                break


class TrieNodeRequestTracker:

    def __init__(self, reply_timeout: int, logger: TraceLogger) -> None:
        self.reply_timeout = reply_timeout
        self.logger = logger
        self.active_requests: Dict[ETHPeer, Tuple[float, List[Hash32]]] = {}
        self.missing: Dict[float, List[Hash32]] = {}

    def get_timed_out(self) -> List[Hash32]:
        timed_out = cytoolz.valfilter(
            lambda v: time.time() - v[0] > self.reply_timeout, self.active_requests)
        for peer, (_, node_keys) in timed_out.items():
            self.logger.debug(
                "Timed out waiting for %d nodes from %s", len(node_keys), peer)
        self.active_requests = cytoolz.dissoc(self.active_requests, *timed_out.keys())
        return list(cytoolz.concat(node_keys for _, node_keys in timed_out.values()))

    def get_retriable_missing(self) -> List[Hash32]:
        retriable = cytoolz.keyfilter(
            lambda k: time.time() - k > self.reply_timeout, self.missing)
        self.missing = cytoolz.dissoc(self.missing, *retriable.keys())
        return list(cytoolz.concat(retriable.values()))

    def get_next_timeout(self) -> float:
        active_req_times = [req_time for (req_time, _) in self.active_requests.values()]
        oldest = min(itertools.chain([time.time()], self.missing.keys(), active_req_times))
        return oldest + self.reply_timeout


class StateSync(HexaryTrieSync):

    async def leaf_callback(self, data: bytes, parent: SyncRequest) -> None:
        # TODO: Need to figure out why geth uses 64 as the depth here, and then document it.
        depth = 64
        account = rlp.decode(data, sedes=Account)
        if account.storage_root != BLANK_ROOT_HASH:
            await self.schedule(account.storage_root, parent, depth, leaf_callback=None)
        if account.code_hash != EMPTY_SHA3:
            await self.schedule(account.code_hash, parent, depth, leaf_callback=None, is_raw=True)


def _test() -> None:
    import argparse
    import signal
    from eth.chains.ropsten import RopstenChain, ROPSTEN_VM_CONFIGURATION
    from p2p import ecies
    from p2p.kademlia import Node
    from p2p.peer import DEFAULT_PREFERRED_NODES
    from tests.p2p.integration_test_helpers import (
        FakeAsyncChainDB, FakeAsyncLevelDB, connect_to_peers_loop)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-enode', type=str, required=False, help="The enode we should connect to")
    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.state.StateDownloader').setLevel(log_level)

    db = FakeAsyncLevelDB(args.db)
    chaindb = FakeAsyncChainDB(db)
    network_id = RopstenChain.network_id
    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
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
