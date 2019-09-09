from cancel_token import CancelToken

from eth.abc import AtomicDatabaseAPI
from eth.constants import BLANK_ROOT_HASH

from p2p.service import BaseService

from trinity.chains.base import AsyncChainAPI
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.protocol.eth.peer import ETHPeerPool

from .chain import RegularChainSyncer


class FullChainSyncer(BaseService):

    def __init__(self,
                 chain: AsyncChainAPI,
                 chaindb: BaseAsyncChainDB,
                 base_db: AtomicDatabaseAPI,
                 peer_pool: ETHPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool

    async def _run(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())

        # Ensure we have the state for our current head.
        if head.state_root != BLANK_ROOT_HASH and head.state_root not in self.base_db:
            self.logger.error(
                "Missing state for current head %s, run beam sync instead", head)
            return

        if self.cancel_token.triggered:
            return

        # Now, loop forever, fetching missing blocks and applying them.
        self.logger.info("Starting regular sync; current head: %s", head)
        regular_syncer = RegularChainSyncer(
            self.chain, self.chaindb, self.peer_pool, self.cancel_token)
        await regular_syncer.run()
