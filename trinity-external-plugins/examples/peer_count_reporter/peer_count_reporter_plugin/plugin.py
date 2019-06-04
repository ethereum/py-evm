# This is an example plugin. It is exposed in the docs and intentionally
# uses more concise style for imports

from argparse import ArgumentParser, _SubParsersAction
import asyncio

from lahja import EndpointAPI

from p2p.service import BaseService
from trinity.extensibility import AsyncioIsolatedPlugin
from trinity.protocol.common.events import PeerCountRequest
from trinity._utils.shutdown import exit_with_services


class PeerCountReporter(BaseService):

    def __init__(self, event_bus: EndpointAPI) -> None:
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


class PeerCountReporterPlugin(AsyncioIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Peer Count Reporter"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--report-peer-count",
            action="store_true",
            help="Report peer count to console",
        )

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        if self.boot_info.args.report_peer_count:
            self.start()

    def do_start(self) -> None:
        service = PeerCountReporter(self.event_bus)
        asyncio.ensure_future(exit_with_services(service, self._event_bus_service))
        asyncio.ensure_future(service.run())
