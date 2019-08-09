from lahja import EndpointAPI
from cancel_token import CancelToken

from eth.abc import AtomicDatabaseAPI

from p2p.service import BaseService

from trinity.chains.base import AsyncChainAPI
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.sync.common.checkpoint import Checkpoint

from .chain import BeamSyncer


class BeamSyncService(BaseService):

    def __init__(
            self,
            chain: AsyncChainAPI,
            chaindb: BaseAsyncChainDB,
            base_db: AtomicDatabaseAPI,
            peer_pool: ETHPeerPool,
            event_bus: EndpointAPI,
            checkpoint: Checkpoint = None,
            force_beam_block_number: int = None,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.chaindb = chaindb
        self.base_db = base_db
        self.peer_pool = peer_pool
        self.event_bus = event_bus
        self.checkpoint = checkpoint
        self.force_beam_block_number = force_beam_block_number

    async def _run(self) -> None:
        head = await self.wait(self.chaindb.coro_get_canonical_head())

        if self.checkpoint is not None:
            self.logger.info(
                "Starting beam-sync; current head: %s, using checkpoint: %s", head, self.checkpoint
            )
        else:
            self.logger.info("Starting beam-sync; current head: %s", head)

        beam_syncer = BeamSyncer(
            self.chain,
            self.base_db,
            self.chaindb,
            self.peer_pool,
            self.event_bus,
            self.checkpoint,
            self.force_beam_block_number,
            token=self.cancel_token,
        )
        await beam_syncer.run()
