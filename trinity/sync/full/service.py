import logging
import time

from cancel_token import CancelToken

from eth.constants import BLANK_ROOT_HASH
from eth.db.backends.base import BaseAtomicDB
from eth.rlp.headers import BlockHeader

from p2p.service import BaseService

from trinity.chains.base import AsyncChainAPI
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.protocol.eth.peer import ETHPeerPool

from .chain import FastChainSyncer, RegularChainSyncer
from .constants import FAST_SYNC_CUTOFF
from .state import StateDownloader


async def ensure_state_then_sync_full(logger: logging.Logger,
                                      head: BlockHeader,
                                      base_db: BaseAtomicDB,
                                      chaindb: BaseAsyncChainDB,
                                      chain: AsyncChainAPI,
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
                 chain: AsyncChainAPI,
                 chaindb: BaseAsyncChainDB,
                 base_db: BaseAtomicDB,
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
                 chain: AsyncChainAPI,
                 chaindb: BaseAsyncChainDB,
                 base_db: BaseAtomicDB,
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
