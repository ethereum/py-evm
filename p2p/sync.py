import logging
import time
from typing import TYPE_CHECKING

from eth.chains import AsyncChain
from eth.constants import BLANK_ROOT_HASH
from eth.db.backends.base import BaseDB

from p2p.cancel_token import CancelToken
from p2p.peer import PeerPool
from p2p.chain import FastChainSyncer, RegularChainSyncer
from p2p.service import BaseService
from p2p.state import StateDownloader


if TYPE_CHECKING:
    from trinity.db.chain import AsyncChainDB  # noqa: F401


# How old (in seconds) must our local head be to cause us to start with a fast-sync before we
# switch to regular-sync.
FAST_SYNC_CUTOFF = 60 * 60 * 24


class FullNodeSyncer(BaseService):
    chain: AsyncChain = None
    chaindb: 'AsyncChainDB' = None
    base_db: BaseDB = None
    peer_pool: PeerPool = None

    def __init__(self,
                 chain: AsyncChain,
                 chaindb: 'AsyncChainDB',
                 base_db: BaseDB,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool

    async def _run(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())
        # We're still too slow at block processing, so if our local head is older than
        # FAST_SYNC_CUTOFF we first do a fast-sync run to catch up with the rest of the network.
        # See https://github.com/ethereum/py-evm/issues/654 for more details
        if head.timestamp < time.time() - FAST_SYNC_CUTOFF:
            # Fast-sync chain data.
            self.logger.info("Starting fast-sync; current head: #%d", head.block_number)
            chain_syncer = FastChainSyncer(
                self.chain, self.chaindb, self.peer_pool, self.cancel_token)
            await chain_syncer.run()

        # Ensure we have the state for our current head.
        head = await self.wait(self.chaindb.coro_get_canonical_head())
        if head.state_root != BLANK_ROOT_HASH and head.state_root not in self.base_db:
            self.logger.info(
                "Missing state for current head (#%d), downloading it", head.block_number)
            downloader = StateDownloader(
                self.chaindb, self.base_db, head.state_root, self.peer_pool, self.cancel_token)
            await downloader.run()

        # Now, loop forever, fetching missing blocks and applying them.
        self.logger.info("Starting regular sync; current head: #%d", head.block_number)
        chain_syncer = RegularChainSyncer(
            self.chain, self.chaindb, self.peer_pool, self.cancel_token)
        await chain_syncer.run()

    async def _cleanup(self) -> None:
        # We don't run anything in the background, so nothing to do here.
        pass


def _test() -> None:
    import argparse
    import asyncio
    from concurrent.futures import ProcessPoolExecutor
    import signal
    from p2p import ecies
    from p2p.kademlia import Node
    from p2p.peer import ETHPeer, DEFAULT_PREFERRED_NODES
    from eth.chains.ropsten import RopstenChain, ROPSTEN_VM_CONFIGURATION
    from eth.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import (
        FakeAsyncChainDB, FakeAsyncRopstenChain, connect_to_peers_loop)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-enode', type=str, required=False, help="The enode we should connect to")
    args = parser.parse_args()

    chaindb = FakeAsyncChainDB(LevelDB(args.db))
    chain = FakeAsyncRopstenChain(chaindb)
    network_id = RopstenChain.network_id
    privkey = ecies.generate_privkey()
    peer_pool = PeerPool(ETHPeer, chaindb, network_id, privkey, ROPSTEN_VM_CONFIGURATION)
    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
        nodes = DEFAULT_PREFERRED_NODES[network_id]
    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, nodes))

    loop = asyncio.get_event_loop()
    loop.set_default_executor(ProcessPoolExecutor())

    syncer = FullNodeSyncer(chain, chaindb, chaindb.db, peer_pool)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await syncer.cancel()
        await peer_pool.cancel()
        loop.stop()

    loop.set_debug(True)
    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(syncer.run())
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    _test()
