# This is an example plugin. It is exposed in the docs and intentionally
# uses more concise style for imports

from argparse import ArgumentParser, _SubParsersAction
import asyncio

from p2p.events import PeerCountRequest
from p2p.service import BaseService
from lahja import Endpoint
from trinity.extensibility import BaseIsolatedPlugin
from trinity._utils.shutdown import exit_with_service_and_endpoint


class PeerCountReporter(BaseService):

    def __init__(self, event_bus: Endpoint) -> None:
        super().__init__()
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.run_daemon_task(self._periodically_report_stats())
        await self.cancel_token.wait()

    async def _periodically_report_stats(self) -> None:
        while self.is_operational:
            try:
                response = await asyncio.wait_for(
                    self.event_bus.request(PeerCountRequest()),
                    timeout=1.0
                )
                self.logger.info("CONNECTED PEERS: %s", response.peer_count)
            except asyncio.TimeoutError:
                self.logger.warning("TIMEOUT: Waiting on PeerPool to boot")
            await asyncio.sleep(5)


class PeerCountReporterPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Peer Count Reporter"

    def configure_parser(self,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--report-peer-count",
            action="store_true",
            help="Report peer count to console",
        )

    def on_ready(self) -> None:
        if self.context.args.report_peer_count:
            self.start()

    def do_start(self) -> None:
        loop = asyncio.get_event_loop()
        service = PeerCountReporter(self.event_bus)
        asyncio.ensure_future(exit_with_service_and_endpoint(service, self.event_bus))
        asyncio.ensure_future(service.run())
        loop.run_forever()
        loop.close()
