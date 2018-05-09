import logging
import time

from evm.chains import AsyncChain
from evm.db.backends.base import BaseDB
from evm.db.chain import AsyncChainDB
from p2p.cancel_token import CancelToken
from p2p.exceptions import OperationCancelled
from p2p.peer import PeerPool
from p2p.chain import FastChainSyncer, RegularChainSyncer
from p2p.state import StateDownloader


# How old (in seconds) must our local head be to cause us to start with a fast-sync before we
# switch to regular-sync.
FAST_SYNC_CUTOFF = 60 * 60 * 24


class FullNodeSyncer:
    logger = logging.getLogger("p2p.sync.FullNodeSyncer")

    def __init__(self,
                 chain: AsyncChain,
                 chaindb: AsyncChainDB,
                 db: BaseDB,
                 peer_pool: PeerPool) -> None:
        self.chain = chain
        self.chaindb = chaindb
        self.db = db
        self.peer_pool = peer_pool
        self.cancel_token = CancelToken('FullNodeSyncer')

    async def run(self) -> None:
        head = await self.chaindb.coro_get_canonical_head()
        # We're still too slow at block processing, so if our local head is older than
        # FAST_SYNC_CUTOFF we first do a fast-sync run to catch up with the rest of the network.
        # See https://github.com/ethereum/py-evm/issues/654 for more details
        if head.timestamp < time.time() - FAST_SYNC_CUTOFF:
            # Fast-sync chain data.
            self.logger.info("Starting fast-sync; current head: #%d", head.block_number)
            chain_syncer = FastChainSyncer(self.chaindb, self.peer_pool, self.cancel_token)
            try:
                await chain_syncer.run()
            finally:
                await chain_syncer.stop()

            # Download state for our current head.
            head = await self.chaindb.coro_get_canonical_head()
            downloader = StateDownloader(
                self.db, head.state_root, self.peer_pool, self.cancel_token)
            try:
                await downloader.run()
            finally:
                await downloader.stop()

        # Now, loop forever, fetching missing blocks and applying them.
        self.logger.info("Starting regular sync; current head: #%d", head.block_number)
        chain_syncer = RegularChainSyncer(
            self.chain, self.chaindb, self.peer_pool, self.cancel_token)
        try:
            await chain_syncer.run()
        finally:
            await chain_syncer.stop()

    async def stop(self):
        self.cancel_token.trigger()


def _test():
    import argparse
    import asyncio
    from concurrent.futures import ProcessPoolExecutor
    import signal
    from p2p import ecies
    from p2p.peer import ETHPeer, HardCodedNodesPeerPool
    from evm.chains.ropsten import RopstenChain
    from evm.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB, FakeAsyncRopstenChain
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    args = parser.parse_args()

    chaindb = FakeAsyncChainDB(LevelDB(args.db))
    chain = FakeAsyncRopstenChain(chaindb)
    peer_pool = HardCodedNodesPeerPool(
        ETHPeer, chaindb, RopstenChain.network_id, ecies.generate_privkey(), min_peers=5)
    asyncio.ensure_future(peer_pool.run())

    loop = asyncio.get_event_loop()
    loop.set_default_executor(ProcessPoolExecutor())

    syncer = FullNodeSyncer(chain, chaindb, chaindb.db, peer_pool)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, syncer.cancel_token.trigger)

    async def run():
        try:
            await syncer.run()
        except OperationCancelled:
            pass
        await peer_pool.stop()

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
