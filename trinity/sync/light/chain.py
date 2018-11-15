from trinity.protocol.les.monitors import LightChainTipMonitor
from trinity.sync.common.chain import BaseHeaderChainSyncer
from trinity.utils.timer import Timer


class LightChainSyncer(BaseHeaderChainSyncer):
    _exit_on_sync_complete = False

    tip_monitor_class = LightChainTipMonitor

    async def _run(self) -> None:
        self.run_task(self._persist_headers())
        await super()._run()

    async def _persist_headers(self) -> None:
        while self.is_operational:
            batch_id, headers = await self.wait(self.header_queue.get())

            timer = Timer()
            await self.wait(self.db.coro_persist_header_chain(headers))

            head = await self.wait(self.db.coro_get_canonical_head())
            self.logger.info(
                "Imported %d headers in %0.2f seconds, new head: %s",
                len(headers), timer.elapsed, head)

            self.header_queue.complete(batch_id, headers)
