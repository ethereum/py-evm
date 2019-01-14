import logging
import time

from cancel_token import CancelToken

from eth.constants import BLANK_ROOT_HASH
from eth.rlp.headers import BlockHeader

from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.db.base import BaseAsyncDB
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.protocol.eth.peer import ETHPeerPool

from .chain import FastChainSyncer, RegularChainSyncer
from .constants import FAST_SYNC_CUTOFF
from .state import StateDownloader


async def ensure_state_then_sync_full(logger: logging.Logger,
                                      head: BlockHeader,
                                      base_db: BaseAsyncDB,
                                      chaindb: BaseAsyncChainDB,
                                      chain: BaseAsyncChain,
                                      peer_pool: ETHPeerPool,
                                      cancel_token: CancelToken) -> None:
    # Ensure we have the state for our current head.
    if head.state_root != BLANK_ROOT_HASH and head.state_root not in base_db:
        logger.info(
            "Missing state for current head %s, downloading it", head)
        downloader = StateDownloader(chaindb, base_db, head.state_root, peer_pool, cancel_token)
        await downloader.run()
        # remove the reference so the memory can be reclaimed
        del downloader

    if cancel_token.triggered:
        return

    # Now, loop forever, fetching missing blocks and applying them.
    logger.info("Starting regular sync; current head: %s", head)
    regular_syncer = RegularChainSyncer(
        chain, chaindb, peer_pool, cancel_token)
    await regular_syncer.run()


class FullChainSyncer(BaseService):

    def __init__(self,
                 chain: BaseAsyncChain,
                 chaindb: BaseAsyncChainDB,
                 base_db: BaseAsyncDB,
                 peer_pool: ETHPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool

    async def _run(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())

        if self.cancel_token.triggered:
            return

        await ensure_state_then_sync_full(
            self.logger,
            head,
            self.base_db,
            self.chaindb,
            self.chain,
            self.peer_pool,
            self.cancel_token
        )


class FastThenFullChainSyncer(BaseService):

    def __init__(self,
                 chain: BaseAsyncChain,
                 chaindb: BaseAsyncChainDB,
                 base_db: BaseAsyncDB,
                 peer_pool: ETHPeerPool,
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
            self.logger.info("Starting fast-sync; current head: %s", head)
            fast_syncer = FastChainSyncer(
                self.chain,
                self.chaindb,
                self.peer_pool,
                self.cancel_token,
            )
            await fast_syncer.run()

            previous_head = head
            head = await self.wait(self.chaindb.coro_get_canonical_head())
            self.logger.info(
                "Finished fast fast-sync; previous head: %s, current head: %s", previous_head, head
            )

            if not fast_syncer.is_complete:
                self.logger.warning("Fast syncer completed abnormally. Exiting...")
                self.cancel_nowait()
                return

            # remove the reference so the memory can be reclaimed
            del fast_syncer

        if self.cancel_token.triggered:
            return

        await ensure_state_then_sync_full(
            self.logger,
            head,
            self.base_db,
            self.chaindb,
            self.chain,
            self.peer_pool,
            self.cancel_token
        )


def _test() -> None:
    import argparse
    import asyncio
    import signal
    from eth.chains.ropsten import ROPSTEN_VM_CONFIGURATION
    from eth.db.backends.level import LevelDB
    from p2p import ecies
    from p2p.kademlia import Node
    from trinity.constants import DEFAULT_PREFERRED_NODES, ROPSTEN_NETWORK_ID
    from trinity.protocol.common.context import ChainContext
    from tests.core.integration_test_helpers import (
        FakeAsyncChainDB, FakeAsyncRopstenChain, connect_to_peers_loop)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-enode', type=str, required=False, help="The enode we should connect to")
    args = parser.parse_args()

    chaindb = FakeAsyncChainDB(LevelDB(args.db))
    chain = FakeAsyncRopstenChain(chaindb)
    network_id = ROPSTEN_NETWORK_ID
    privkey = ecies.generate_privkey()

    context = ChainContext(
        headerdb=chaindb,
        network_id=network_id,
        vm_configuration=ROPSTEN_VM_CONFIGURATION
    )
    peer_pool = ETHPeerPool(privkey=privkey, context=context)
    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
        nodes = DEFAULT_PREFERRED_NODES[network_id]
    asyncio.ensure_future(peer_pool.run())
    peer_pool.run_task(connect_to_peers_loop(peer_pool, nodes))

    loop = asyncio.get_event_loop()

    syncer = FastThenFullChainSyncer(chain, chaindb, chaindb.db, peer_pool)

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
