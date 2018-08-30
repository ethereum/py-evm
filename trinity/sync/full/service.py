import logging
import time

from cancel_token import CancelToken

from eth.chains import AsyncChain
from eth.constants import BLANK_ROOT_HASH

from p2p.service import BaseService
from p2p.peer import PeerPool

from trinity.db.base import AsyncBaseDB
from trinity.db.chain import AsyncChainDB

from .chain import FastChainSyncer, RegularChainSyncer
from .constants import (
    FAST_SYNC_CUTOFF,
    STALE_STATE_ROOT_AGE,
)
from .state import StateDownloader


class FullNodeSyncer(BaseService):
    chain: AsyncChain = None
    chaindb: AsyncChainDB = None
    base_db: AsyncBaseDB = None
    peer_pool: PeerPool = None

    def __init__(self,
                 chain: AsyncChain,
                 chaindb: AsyncChainDB,
                 base_db: AsyncBaseDB,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool

    async def _run(self) -> None:
        if await self.should_fast_sync():
            await self.do_fast_sync()

        if self.is_operational:
            await self.do_regular_sync()

    async def should_fast_sync(self) -> bool:
        head = await self.wait(self.chaindb.coro_get_canonical_head())
        # We're still too slow at block processing, so if our local head is older than
        # FAST_SYNC_CUTOFF we first do a fast-sync run to catch up with the rest of the network.
        # See https://github.com/ethereum/py-evm/issues/654 for more details
        if head.timestamp < time.time() - FAST_SYNC_CUTOFF:
            return True
        elif head.state_root != BLANK_ROOT_HASH and head.state_root not in self.base_db:
            return True
        else:
            return False

    async def _update_downloader_state_root(self,
                                            chain_syncer: FastChainSyncer,
                                            downloader: StateDownloader) -> None:
        # TODO: remove this initial wait
        target = await chain_syncer.wait_new_sync_target()

        while self.is_operational:
            # TODO: exit when downloader has finished.
            new_target = await chain_syncer.wait_new_sync_target()
            self.logger('new target: #%d !!!!!!!!!!!!!!!!!!!', new_target.block_number)
            # we only update the state root for the chain syncer when the new
            # head is at least STALE_STATE_ROOT_AGE in the future of the
            # previous state sync head
            if new_target.block_number - target.block_number < STALE_STATE_ROOT_AGE:
                self.logger('not updating to new target!!!!!!!!!!!!!!!!!')
                continue
            target = new_target
            await downloader.update_state_root(target.state_root)

    async def do_fast_sync(self) -> None:
        chain_syncer = FastChainSyncer(
            self.chain, self.chaindb, self.peer_pool, self.cancel_token)
        self.run_daemon(chain_syncer)
        target = await chain_syncer.wait_new_sync_target()
        downloader = StateDownloader(
            self.chaindb, self.base_db, target.state_root, self.peer_pool, self.cancel_token)
        self.run_task(self._update_downloader_state_root(chain_syncer, downloader))
        await downloader.run()

    async def do_regular_sync(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())
        # Now, loop forever, fetching missing blocks and applying them.
        self.logger.info("Starting regular sync; current head: #%d", head.block_number)
        chain_syncer = RegularChainSyncer(
            self.chain, self.chaindb, self.peer_pool, self.cancel_token)
        await chain_syncer.run()


def _test() -> None:
    import argparse
    import asyncio
    import signal
    from eth.chains.ropsten import RopstenChain, ROPSTEN_VM_CONFIGURATION
    from eth.db.backends.level import LevelDB
    from p2p import ecies
    from p2p.kademlia import Node
    from p2p.peer import DEFAULT_PREFERRED_NODES
    from trinity.protocol.eth.peer import ETHPeer
    from tests.trinity.core.integration_test_helpers import (
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
    peer_pool.run_task(connect_to_peers_loop(peer_pool, nodes))

    loop = asyncio.get_event_loop()

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
