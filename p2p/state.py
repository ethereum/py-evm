import asyncio
import logging
import time
from typing import (  # noqa: F401
    Any,
    cast,
    Dict,
    List,
    Set,
)

import rlp

from trie.sync import HexaryTrieSync
from trie.exceptions import SyncRequestAlreadyProcessed

from eth_keys import datatypes  # noqa: F401
from eth_utils import (
    decode_hex,
    encode_hex,
    keccak,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.db.backends.base import BaseDB
from evm.rlp.accounts import Account

from p2p import eth
from p2p.cancel_token import CancelToken
from p2p.exceptions import OperationCancelled
from p2p.peer import BasePeer, ETHPeer, PeerPool, PeerPoolSubscriber
from p2p.eth import MAX_STATE_FETCH


class StateDownloader(PeerPoolSubscriber):
    logger = logging.getLogger("p2p.state.StateDownloader")
    _pending_nodes = {}  # type: Dict[Any, float]
    _total_processed_nodes = 0
    _report_interval = 10  # Number of seconds between progress reports.
    # TODO: Experiment with different timeout/max_pending values to find the combination that
    # yields the best results.
    # FIXME: Should use the # of peers times MAX_STATE_FETCH here
    _max_pending = 5 * MAX_STATE_FETCH
    _reply_timeout = 10  # seconds
    # For simplicity/readability we use 0 here to force a report on the first iteration of the
    # loop.
    _last_report_time = 0

    def __init__(self, state_db: BaseDB, root_hash: bytes, peer_pool: PeerPool) -> None:
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self.root_hash = root_hash
        self.scheduler = StateSync(root_hash, state_db, self.logger)
        self._running_peers = set()  # type: Set[ETHPeer]
        self.cancel_token = CancelToken('StateDownloader')

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(ETHPeer, peer)))

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
            if isinstance(cmd, eth.NodeData):
                self.logger.debug("Processing NodeData with %d entries", len(msg))
                for node in msg:
                    self._total_processed_nodes += 1
                    node_key = keccak(node)
                    try:
                        self.scheduler.process([(node_key, node)])
                    except SyncRequestAlreadyProcessed:
                        # This means we received a node more than once, which can happen when we
                        # retry after a timeout.
                        pass
                    # A node may be received more than once, so pop() with a default value.
                    self._pending_nodes.pop(node_key, None)
            else:
                # It'd be very convenient if we could ignore everything that is not a NodeData
                # when doing a StateSync, but need to double check because peers may consider that
                # "Bad Form" and disconnect from us.
                self.logger.debug("Ignoring %s(%s) while doing a StateSync", cmd, msg)

    async def stop(self):
        self.cancel_token.trigger()
        self.peer_pool.unsubscribe(self)
        while self._running_peers:
            self.logger.debug("Waiting for %d running peers to finish", len(self._running_peers))
            await asyncio.sleep(0.1)

    async def request_next_batch(self):
        requests = self.scheduler.next_batch(MAX_STATE_FETCH)
        if not requests:
            # Although our run() loop frequently yields control to let our msg handler process
            # received nodes (scheduling new requests), there may be cases when the pending nodes
            # take a while to arrive thus causing the scheduler to run out of new requests for a
            # while.
            self.logger.debug("Scheduler queue is empty, not requesting any nodes")
            return
        self.logger.debug("Requesting %d trie nodes", len(requests))
        await self.request_nodes([request.node_key for request in requests])

    async def request_nodes(self, node_keys: List[bytes]) -> None:
        # FIXME: Need a better criteria to select peers here.
        peer = await self.peer_pool.get_random_peer()
        now = time.time()
        for node_key in node_keys:
            self._pending_nodes[node_key] = now
        cast(ETHPeer, peer).sub_proto.send_get_node_data(node_keys)

    async def retry_timedout(self):
        timed_out = []
        now = time.time()
        for node_key, req_time in list(self._pending_nodes.items()):
            if now - req_time > self._reply_timeout:
                timed_out.append(node_key)
        if not timed_out:
            return
        self.logger.debug("Re-requesting %d trie nodes", len(timed_out))
        await self.request_nodes(timed_out)

    async def run(self):
        self.logger.info("Starting state sync for root hash %s", encode_hex(self.root_hash))
        while self.scheduler.has_pending_requests and not self.cancel_token.triggered:
            # Request new nodes if we haven't reached the limit of pending nodes.
            if len(self._pending_nodes) < self._max_pending:
                await self.request_next_batch()

            # Retry pending nodes that timed out.
            if self._pending_nodes:
                await self.retry_timedout()

            if len(self._pending_nodes) > self._max_pending:
                # Slow down if we've reached the limit of pending nodes.
                self.logger.debug("Pending trie nodes limit reached, sleeping a bit")
                await asyncio.sleep(0.3)
            else:
                # Yield control to ensure the Peer's msg_handler callback is called to process any
                # nodes we may have received already. Otherwise we spin too fast and don't process
                # received nodes often enough.
                await asyncio.sleep(0)

            self._maybe_report_progress()

        self.logger.info("Finished state sync with root hash %s", encode_hex(self.root_hash))

    def _maybe_report_progress(self):
        if (time.time() - self._last_report_time) >= self._report_interval:
            self._last_report_time = time.time()
            self.logger.info("Nodes processed: %d", self._total_processed_nodes)
            self.logger.info(
                "Nodes requested but not received yet: %d", len(self._pending_nodes))
            self.logger.info(
                "Nodes scheduled but not requested yet: %d", len(self.scheduler.requests))


class StateSync(HexaryTrieSync):

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
    import signal
    from p2p import ecies
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
    from evm.db.backends.level import LevelDB
    from evm.db.backends.memory import MemoryDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-root-hash', type=str, required=True, help='Hex encoded root hash')
    args = parser.parse_args()

    chaindb = FakeAsyncChainDB(MemoryDB())
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    peer_pool = PeerPool(ETHPeer, chaindb, RopstenChain.network_id, ecies.generate_privkey())
    asyncio.ensure_future(peer_pool.run())

    state_db = LevelDB(args.db)
    root_hash = decode_hex(args.root_hash)
    downloader = StateDownloader(state_db, root_hash, peer_pool)
    loop = asyncio.get_event_loop()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, downloader.cancel_token.trigger)

    async def run():
        # downloader.run() will run in a loop until the SIGINT/SIGTERM handler triggers its cancel
        # token, at which point it returns and we stop the pool and downloader.
        await downloader.run()
        await peer_pool.stop()
        await downloader.stop()

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
