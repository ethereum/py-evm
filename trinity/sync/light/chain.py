from cancel_token import CancelToken


from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.les.peer import LESPeerPool
from trinity.protocol.les.sync import LightHeaderChainSyncer
from trinity._utils.timer import Timer


class LightChainSyncer(BaseService):
    def __init__(self,
                 chain: BaseAsyncChain,
                 db: BaseAsyncHeaderDB,
                 peer_pool: LESPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token=token)
        self._db = db
        self._header_syncer = LightHeaderChainSyncer(chain, db, peer_pool, self.cancel_token)

    async def _run(self) -> None:
        self.run_daemon(self._header_syncer)
        self.run_daemon_task(self._persist_headers())
        # run sync until cancelled
        await self.events.cancelled.wait()

    async def _persist_headers(self) -> None:
        async for headers in self._header_syncer.new_sync_headers():
            timer = Timer()
            await self.wait(self._db.coro_persist_header_chain(headers))

            head = await self.wait(self._db.coro_get_canonical_head())
            self.logger.info(
                "Imported %d headers in %0.2f seconds, new head: %s",
                len(headers), timer.elapsed, head)
