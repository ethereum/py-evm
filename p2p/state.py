import asyncio
import logging
import secrets
import time
from typing import (  # noqa: F401
    Any,
    cast,
    Dict,
    List,
    Set,
)

from cytoolz.itertoolz import partition_all

import rlp

from trie.sync import HexaryTrieSync
from trie.exceptions import SyncRequestAlreadyProcessed

from eth_utils import (
    encode_hex,
)

from eth_hash.auto import keccak

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.db.backends.base import BaseDB
from evm.rlp.accounts import Account

from p2p import eth
from p2p import protocol
from p2p.cancel_token import CancelToken, wait_with_token
from p2p.exceptions import OperationCancelled
from p2p.peer import BasePeer, ETHPeer, PeerPool, PeerPoolSubscriber


class StateDownloader(PeerPoolSubscriber):
    logger = logging.getLogger("p2p.state.StateDownloader")
    _pending_nodes = {}  # type: Dict[Any, float]
    _total_processed_nodes = 0
    _report_interval = 10  # Number of seconds between progress reports.
    _reply_timeout = 20  # seconds
    _start_time = None  # type: float
    _total_timeouts = 0

    def __init__(self,
                 account_db: BaseDB,
                 root_hash: bytes,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self.root_hash = root_hash
        self.scheduler = StateSync(root_hash, account_db)
        self._running_peers = set()  # type: Set[ETHPeer]
        self._peers_with_pending_requests = {}  # type: Dict[ETHPeer, float]
        self.cancel_token = CancelToken('StateDownloader')
        if token is not None:
            self.cancel_token = self.cancel_token.chain(token)

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(ETHPeer, peer)))

    @property
    def idle_peers(self) -> List[ETHPeer]:
        peers = set([cast(ETHPeer, peer) for peer in self.peer_pool.peers])
        return list(peers.difference(self._peers_with_pending_requests))

    async def get_idle_peer(self) -> ETHPeer:
        while not self.idle_peers:
            self.logger.debug("Waiting for an idle peer...")
            await wait_with_token(asyncio.sleep(0.02), token=self.cancel_token)
        return secrets.choice(self.idle_peers)

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

            # Run self._handle_msg() with ensure_future() instead of awaiting for it so that we
            # can keep consuming msgs while _handle_msg() performs cpu-intensive tasks in separate
            # processes.
            asyncio.ensure_future(self._handle_msg(peer, cmd, msg))

    async def _handle_msg(
            self, peer: ETHPeer, cmd: protocol.Command, msg: protocol._DecodedMsgType) -> None:
        loop = asyncio.get_event_loop()
        if isinstance(cmd, eth.NodeData):
            self.logger.debug("Got %d NodeData entries from %s", len(msg), peer)

            # Check before we remove because sometimes a reply may come after our timeout and in
            # that case we won't be expecting it anymore.
            if peer in self._peers_with_pending_requests:
                self._peers_with_pending_requests.pop(peer)

            node_keys = await loop.run_in_executor(None, list, map(keccak, msg))
            for node_key, node in zip(node_keys, msg):
                self._total_processed_nodes += 1
                try:
                    self.scheduler.process([(node_key, node)])
                except SyncRequestAlreadyProcessed:
                    # This means we received a node more than once, which can happen when we
                    # retry after a timeout.
                    pass
                # A node may be received more than once, so pop() with a default value.
                self._pending_nodes.pop(node_key, None)
        else:
            # We ignore everything that is not a NodeData when doing a StateSync.
            self.logger.debug("Ignoring %s msg while doing a StateSync", cmd)

    async def stop(self):
        self.cancel_token.trigger()
        self.peer_pool.unsubscribe(self)
        while self._running_peers:
            self.logger.debug("Waiting for %d running peers to finish", len(self._running_peers))
            await asyncio.sleep(0.1)

    async def request_nodes(self, node_keys: List[bytes]) -> None:
        batches = list(partition_all(eth.MAX_STATE_FETCH, node_keys))
        for batch in batches:
            peer = await self.get_idle_peer()
            now = time.time()
            for node_key in batch:
                self._pending_nodes[node_key] = now
            self.logger.debug("Requesting %d trie nodes to %s", len(batch), peer)
            peer.sub_proto.send_get_node_data(batch)
            self._peers_with_pending_requests[peer] = now

    async def _periodically_retry_timedout(self):
        while True:
            now = time.time()
            # First, update our list of peers with pending requests by removing those for which a
            # request timed out. This loop mutates the dict, so we iterate on a copy of it.
            for peer, last_req_time in list(self._peers_with_pending_requests.items()):
                if now - last_req_time > self._reply_timeout:
                    self._peers_with_pending_requests.pop(peer)

            # Now re-send requests for nodes that timed out.
            oldest_request_time = now
            timed_out = []
            for node_key, req_time in self._pending_nodes.items():
                if now - req_time > self._reply_timeout:
                    timed_out.append(node_key)
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
                await wait_with_token(asyncio.sleep(sleep_duration), token=self.cancel_token)
            except OperationCancelled:
                break

    async def run(self):
        """Fetch all trie nodes starting from self.root_hash, and store them in self.db.

        Raises OperationCancelled if we're interrupted before that is completed.
        """
        self._start_time = time.time()
        self.logger.info("Starting state sync for root hash %s", encode_hex(self.root_hash))
        asyncio.ensure_future(self._periodically_report_progress())
        asyncio.ensure_future(self._periodically_retry_timedout())
        while self.scheduler.has_pending_requests:
            # This ensures we yield control and give _handle_msg() a chance to process any nodes
            # we may have received already, also ensuring we exit when our cancel token is
            # triggered.
            await wait_with_token(asyncio.sleep(0), token=self.cancel_token)

            requests = self.scheduler.next_batch(eth.MAX_STATE_FETCH)
            if not requests:
                # Although we frequently yield control above, to let our msg handler process
                # received nodes (scheduling new requests), there may be cases when the
                # pending nodes take a while to arrive thus causing the scheduler to run out
                # of new requests for a while.
                self.logger.info("Scheduler queue is empty, sleeping a bit")
                await wait_with_token(asyncio.sleep(0.5), token=self.cancel_token)
                continue

            await self.request_nodes([request.node_key for request in requests])

        self.logger.info("Finished state sync with root hash %s", encode_hex(self.root_hash))

    async def _periodically_report_progress(self):
        while True:
            now = time.time()
            self.logger.info("====== State sync progress ========")
            self.logger.info("Nodes processed: %d", self._total_processed_nodes)
            self.logger.info("Nodes processed per second (average): %d",
                             self._total_processed_nodes / (now - self._start_time))
            self.logger.info("Nodes committed to DB: %d", self.scheduler.committed_nodes)
            self.logger.info(
                "Nodes requested but not received yet: %d", len(self._pending_nodes))
            self.logger.info(
                "Nodes scheduled but not requested yet: %d", len(self.scheduler.requests))
            self.logger.info("Total nodes timed out: %d", self._total_timeouts)
            try:
                await wait_with_token(asyncio.sleep(self._report_interval), token=self.cancel_token)
            except OperationCancelled:
                break


class StateSync(HexaryTrieSync):

    def __init__(self, root_hash, db):
        super().__init__(root_hash, db, logging.getLogger("p2p.state.StateSync"))

    def leaf_callback(self, data, parent):
        # TODO: Need to figure out why geth uses 64 as the depth here, and then document it.
        depth = 64
        account = rlp.decode(data, sedes=Account)
        if account.storage_root != BLANK_ROOT_HASH:
            self.schedule(account.storage_root, parent, depth, leaf_callback=None)
        if account.code_hash != EMPTY_SHA3:
            self.schedule(account.code_hash, parent, depth, leaf_callback=None, is_raw=True)


def _test():
    import argparse
    from concurrent.futures import ProcessPoolExecutor
    import signal
    from p2p import ecies
    from p2p.peer import HardCodedNodesPeerPool
    from evm.chains.ropsten import RopstenChain
    from evm.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB
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
    peer_pool = HardCodedNodesPeerPool(
        ETHPeer, chaindb, RopstenChain.network_id, ecies.generate_privkey(), min_peers=5)
    asyncio.ensure_future(peer_pool.run())

    head = chaindb.get_canonical_head()
    downloader = StateDownloader(db, head.state_root, peer_pool)
    loop = asyncio.get_event_loop()
    loop.set_default_executor(ProcessPoolExecutor())

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, downloader.cancel_token.trigger)

    async def run():
        # downloader.run() will run in a loop until the SIGINT/SIGTERM handler triggers its cancel
        # token, at which point it returns and we stop the pool and downloader.
        try:
            await downloader.run()
        except OperationCancelled:
            pass
        await peer_pool.stop()
        await downloader.stop()

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    # Use the snippet below to get profile stats and print the top 50 functions by cumulative time
    # used.
    # import cProfile, pstats  # noqa
    # cProfile.run('_test()', 'stats')
    # pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    _test()
