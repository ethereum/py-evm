from cancel_token import CancelToken

from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.db.base import BaseAsyncDB
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.protocol.eth.peer import ETHPeerPool

from .chain import BeamSyncer


class BeamSyncService(BaseService):

    def __init__(
            self,
            chain: BaseAsyncChain,
            chaindb: BaseAsyncChainDB,
            base_db: BaseAsyncDB,
            peer_pool: ETHPeerPool,
            event_bus: TrinityEventBusEndpoint,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool
        self.event_bus = event_bus

    async def _run(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())
        self.logger.info("Starting beam-sync; current head: %s", head)
        beam_syncer = BeamSyncer(
            self.chain,
            self.base_db,
            self.chaindb,
            self.peer_pool,
            self.event_bus,
            force_beam_block_number=None,
            token=self.cancel_token,
        )
        await beam_syncer.run()
