import asyncio
import logging
import operator
import time
from typing import Any, cast, Dict, List, Set, Tuple  # noqa: F401

from evm.db.chain import AsyncChainDB
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
                self.handle_msg(peer, cmd, msg)
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

            # TODO: If we're in light mode and we've synced up to head - 1024, trigger cancel
            # token to stop and raise an exception to tell our caller it should perform a state
            # sync.

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
            # TODO: Queue body/receipt downloads.
            for header in headers:
                await self.chaindb.coro_persist_header(header)
                start_at = header.block_number

            self.logger.debug("Asking %s for header batch starting at %d", peer, start_at)
            # TODO: Instead of requesting sequential batches from a single peer, request a header
            # skeleton and make concurrent requests, using as many peers as possible, to fill the
            # skeleton.
            peer.sub_proto.send_get_block_headers(start_at, eth.MAX_HEADERS_FETCH, reverse=False)

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

    def handle_msg(self, peer: ETHPeer, cmd: protocol.Command,
                   msg: protocol._DecodedMsgType) -> None:
        if isinstance(cmd, eth.BlockHeaders):
            msg = cast(List[BlockHeader], msg)
            self.logger.debug(
                "Got BlockHeaders from %d to %d", msg[0].block_number, msg[-1].block_number)
            self._new_headers.put_nowait(msg)
        elif isinstance(cmd, eth.BlockBodies):
            # TODO: Queue msg for processing by body downloader.
            pass
        elif isinstance(cmd, eth.Receipts):
            # TODO: Queue msg for processing by receipt downloader.
            pass
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
