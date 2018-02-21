import asyncio
import logging
from typing import (  # noqa: F401
    Any,
    Callable,
    cast,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)

from async_lru import alru_cache

from eth_keys import (  # noqa: F401
    datatypes,
    keys,
)
from eth_utils import (
    encode_hex,
)

from evm.chains import Chain
from evm.constants import GENESIS_BLOCK_NUMBER
from evm.db.chain import ChainDB
from evm.exceptions import (
    BlockNotFound,
)
from evm.rlp.accounts import Account
from evm.rlp.blocks import BaseBlock
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.p2p.exceptions import (
    EmptyGetBlockHeadersReply,
    LESAnnouncementProcessingError,
    PeerFinished,
    StopRequested,
    TooManyTimeouts,
    UnexpectedMessage,
)
from evm.p2p import les
from evm.p2p.peer import (
    BasePeer,
    LESPeer,
    PeerPool,
    PeerPoolSubscriber,
)


class LightChain(Chain, PeerPoolSubscriber):
    logger = logging.getLogger("evm.p2p.lightchain.LightChain")
    max_consecutive_timeouts = 5

    def __init__(self, chaindb: ChainDB, peer_pool: PeerPool) -> None:
        super(LightChain, self).__init__(chaindb)
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self._announcement_queue = asyncio.Queue()  # type: asyncio.Queue[Tuple[LESPeer, les.HeadInfo]]  # noqa: E501
        self._last_processed_announcements = {}  # type: Dict[LESPeer, les.HeadInfo]
        self._should_stop = asyncio.Event()
        self._finished = asyncio.Event()
        self._running_peers = set()  # type: Set[LESPeer]

    @classmethod
    def from_genesis_header(cls, chaindb, genesis_header, peer_pool):
        chaindb.persist_header_to_db(genesis_header)
        return cls(chaindb, peer_pool)

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(LESPeer, peer)))

    async def handle_peer(self, peer: LESPeer) -> None:
        """Handle the lifecycle of the given peer.

        Returns when the peer is finished or when the LightChain is asked to stop.
        """
        self._running_peers.add(peer)
        try:
            await self._handle_peer(peer)
        finally:
            self._running_peers.remove(peer)

    async def _handle_peer(self, peer: LESPeer) -> None:
        self._announcement_queue.put_nowait((peer, peer.head_info))
        while True:
            try:
                cmd, msg = await peer.read_sub_proto_msg()
            except PeerFinished:
                break
            # We currently implement only the LES commands for retrieving data (apart from
            # Announce), and those should always come as a response to requests we make so will be
            # handled by LESPeer.handle_sub_proto_msg().
            if isinstance(cmd, les.Announce):
                peer.head_info = cmd.as_head_info(msg)
                self._announcement_queue.put_nowait((peer, peer.head_info))
            else:
                raise UnexpectedMessage("Unexpected msg from {}: {}".format(peer, msg))

        await self.drop_peer(peer)
        self.logger.debug("%s finished", peer)

    async def drop_peer(self, peer: LESPeer) -> None:
        self._last_processed_announcements.pop(peer, None)
        await peer.stop()

    async def wait_until_finished(self):
        while self._running_peers:
            self.logger.debug("Waiting for %d running peers to finish", len(self._running_peers))
            await asyncio.sleep(0.1)
        await self._finished.wait()

    async def get_best_peer(self) -> LESPeer:
        """
        Return the peer with the highest announced block height.
        """
        while not self.peer_pool.peers:
            self.logger.debug("No connected peers, sleeping a bit")
            await asyncio.sleep(0.5)

        def peer_block_height(peer: LESPeer):
            last_announced = self._last_processed_announcements.get(peer)
            if last_announced is None:
                return -1
            return last_announced.block_number

        # TODO: Should pick a random one in case there are multiple peers with the same block
        # height.
        return max(
            [cast(LESPeer, peer) for peer in self.peer_pool.peers],
            key=peer_block_height)

    async def wait_for_announcement(self) -> Tuple[LESPeer, les.HeadInfo]:
        """Wait for a new announcement from any of our connected peers.

        Returns a tuple containing the LESPeer on which the announcement was received and the
        announcement info.

        Raises StopRequested when LightChain.stop() has been called.
        """
        should_stop = False

        async def wait_for_stop_event():
            nonlocal should_stop
            await self._should_stop.wait()
            should_stop = True

        # Wait for either a new announcement or the _should_stop event.
        done, pending = await asyncio.wait(
            [self._announcement_queue.get(), wait_for_stop_event()],
            return_when=asyncio.FIRST_COMPLETED)
        # The asyncio.wait() call above may return both tasks as done, but never both as pending,
        # although to be future-proof (in case more than 2 tasks are passed in to wait()), we
        # iterate over all pending tasks and cancel all of them.
        for task in pending:
            task.cancel()
        if should_stop:
            raise StopRequested()
        return done.pop().result()

    async def run(self) -> None:
        """Run the LightChain, ensuring headers are in sync with connected peers.

        If .stop() is called, we'll disconnect from all peers and return.
        """
        self.logger.info("Running LightChain...")
        while True:
            try:
                peer, head_info = await self.wait_for_announcement()
            except StopRequested:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break

            try:
                await self.process_announcement(peer, head_info)
                self._last_processed_announcements[peer] = head_info
            except StopRequested:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break
            except LESAnnouncementProcessingError as e:
                self.logger.warning(repr(e))
                await self.drop_peer(peer)
            except Exception as e:
                self.logger.error(
                    "Unexpected error when processing announcement: %s", repr(e))
                await self.drop_peer(peer)

        self._finished.set()

    async def fetch_headers(self, start_block: int, peer: LESPeer) -> List[BlockHeader]:
        for i in range(self.max_consecutive_timeouts):
            if self._should_stop.is_set():
                raise StopRequested()
            try:
                return await peer.fetch_headers_starting_at(start_block)
            except asyncio.TimeoutError:
                self.logger.info(
                    "Timeout when fetching headers from %s (attempt %d of %d)",
                    peer, i + 1, self.max_consecutive_timeouts)
                # TODO: Figure out what's a good value to use here.
                await asyncio.sleep(0.5)
        raise TooManyTimeouts()

    async def get_sync_start_block(self, peer: LESPeer, head_info: les.HeadInfo) -> int:
        chain_head = await self.chaindb.coro_get_canonical_head()
        last_peer_announcement = self._last_processed_announcements.get(peer)
        if chain_head.block_number == GENESIS_BLOCK_NUMBER:
            start_block = GENESIS_BLOCK_NUMBER
        elif last_peer_announcement is None:
            # It's the first time we hear from this peer, need to figure out which headers to
            # get from it.  We can't simply fetch headers starting from our current head
            # number because there may have been a chain reorg, so we fetch some headers prior
            # to our head from the peer, and insert any missing ones in our DB, essentially
            # making our canonical chain identical to the peer's up to
            # chain_head.block_number.
            oldest_ancestor_to_consider = max(
                0, chain_head.block_number - peer.max_headers_fetch + 1)
            try:
                headers = await self.fetch_headers(oldest_ancestor_to_consider, peer)
            except EmptyGetBlockHeadersReply:
                raise LESAnnouncementProcessingError(
                    "No common ancestors found between us and {}".format(peer))
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in headers:
                await self.chaindb.coro_persist_header_to_db(header)
            start_block = chain_head.block_number
        else:
            start_block = last_peer_announcement.block_number - head_info.reorg_depth
        return start_block

    # TODO: Distribute requests among our peers, ensuring the selected peer has the info we want
    # and respecting the flow control rules.
    async def process_announcement(self, peer: LESPeer, head_info: les.HeadInfo) -> None:
        if await self.chaindb.coro_header_exists(head_info.block_hash):
            self.logger.debug(
                "Skipping processing of %s from %s as head has already been fetched",
                head_info, peer)
            return

        start_block = await self.get_sync_start_block(peer, head_info)
        while start_block < head_info.block_number:
            # TODO: Need to check that the peer is not finished (peer._finished.is_set()), because
            # if they are we're going to get errors when trying to use them to make requests.
            try:
                # We should use "start_block + 1" here, but we always re-fetch the last synced
                # block to work around https://github.com/ethereum/go-ethereum/issues/15447
                batch = await self.fetch_headers(start_block, peer)
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in batch:
                await self.chaindb.coro_persist_header_to_db(header)
                start_block = header.block_number
            self.logger.info("synced headers up to #%s", start_block)

    async def stop(self):
        self.logger.info("Stopping LightChain...")
        self._should_stop.set()
        self.logger.debug("Waiting for all pending tasks to finish...")
        await self.wait_until_finished()
        self.logger.debug("LightChain finished")

    async def get_canonical_block_by_number(self, block_number: int) -> BaseBlock:
        """Return the block with the given number from the canonical chain.

        Raises BlockNotFound if it is not found.
        """
        try:
            block_hash = await self.chaindb.coro_lookup_block_hash(block_number)
        except KeyError:
            raise BlockNotFound(
                "No block with number {} found on local chain".format(block_number))
        return await self.get_block_by_hash(block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_by_hash(self, block_hash: bytes) -> BaseBlock:
        peer = await self.get_best_peer()
        try:
            header = await self.chaindb.coro_get_block_header_by_hash(block_hash)
        except BlockNotFound:
            self.logger.debug("Fetching header %s from %s", encode_hex(block_hash), peer)
            header = await peer.get_block_header_by_hash(block_hash)

        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        body = await peer.get_block_by_hash(block_hash)
        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        transactions = [
            block_class.transaction_class.from_base_transaction(tx)
            for tx in body.transactions
        ]
        return block_class(
            header=header,
            transactions=transactions,
            uncles=body.uncles,
        )

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_receipts(self, block_hash: bytes) -> List[Receipt]:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching %s receipts from %s", encode_hex(block_hash), peer)
        return await peer.get_receipts(block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_account(self, block_hash: bytes, address: bytes) -> Account:
        peer = await self.get_best_peer()
        return await peer.get_account(block_hash, address)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_contract_code(self, block_hash: bytes, key: bytes) -> bytes:
        peer = await self.get_best_peer()
        return await peer.get_contract_code(block_hash, key)


def _test():
    import argparse
    import signal
    from evm.chains.mainnet import (
        MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID)
    from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER, ROPSTEN_NETWORK_ID
    from evm.db.backends.level import LevelDB
    from evm.exceptions import CanonicalHeadNotFound
    from evm.p2p import ecies
    from evm.p2p.integration_test_helpers import LocalGethPeerPool

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger("evm.p2p.lightchain.LightChain").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-mainnet', action="store_true")
    parser.add_argument('-local-geth', action="store_true")
    args = parser.parse_args()

    GENESIS_HEADER = ROPSTEN_GENESIS_HEADER
    NETWORK_ID = ROPSTEN_NETWORK_ID
    if args.mainnet:
        GENESIS_HEADER = MAINNET_GENESIS_HEADER
        NETWORK_ID = MAINNET_NETWORK_ID
    DemoLightChain = LightChain.configure(
        'DemoLightChain',
        vm_configuration=MAINNET_VM_CONFIGURATION,
        network_id=NETWORK_ID,
    )

    chaindb = ChainDB(LevelDB(args.db))
    if args.local_geth:
        peer_pool = LocalGethPeerPool(LESPeer, chaindb, NETWORK_ID, ecies.generate_privkey())
    else:
        peer_pool = PeerPool(LESPeer, chaindb, NETWORK_ID, ecies.generate_privkey())
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = DemoLightChain.from_genesis_header(chaindb, GENESIS_HEADER, peer_pool)
    else:
        # We're reusing an existing db.
        chain = DemoLightChain(chaindb, peer_pool)

    asyncio.ensure_future(peer_pool.run())
    loop = asyncio.get_event_loop()

    async def run():
        # chain.run() will run in a loop until stop() (registered as SIGINT/SIGTERM handler) is
        # called, at which point it returns and we cleanly stop the pool and chain.
        await chain.run()
        await peer_pool.stop()
        await chain.stop()

    def stop():
        chain._should_stop.set()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, stop)

    loop.run_until_complete(run())
    loop.close()


if __name__ == '__main__':
    _test()
