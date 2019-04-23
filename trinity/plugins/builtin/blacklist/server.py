from cancel_token import CancelToken

from eth_utils import humanize_seconds

from p2p.service import BaseService
from p2p.tracking.connection import BaseConnectionTracker

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)

from .events import (
    BlacklistEvent,
    ShouldConnectToPeerRequest,
    ShouldConnectToPeerResponse,
)


class BlacklistServer(BaseService):
    """
    Server to handle the event bus communication for BlacklistEvent and
    ShouldConnectToPeerRequest/Response events
    """

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 tracker: BaseConnectionTracker,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.tracker = tracker
        self.event_bus = event_bus

    async def handle_should_connect_to_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(ShouldConnectToPeerRequest)):
            self.logger.debug2('Received should connect to request: %s', req.remote)
            should_connect = self.tracker.should_connect_to(req.remote)
            self.event_bus.broadcast(
                ShouldConnectToPeerResponse(should_connect),
                req.broadcast_config()
            )

    async def handle_blacklist_command(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(BlacklistEvent)):
            self.logger.debug2(
                'Received blacklist commmand: remote: %s | timeout: %s | reason: %s',
                command.remote,
                humanize_seconds(command.timeout),
                command.reason,
            )
            self.tracker.record_blacklist(command.remote, command.timeout, command.reason)

    async def _run(self) -> None:
        self.logger.debug("Running BlacklistServer")

        self.run_daemon_task(self.handle_should_connect_to_requests())
        self.run_daemon_task(self.handle_blacklist_command())

        await self.cancel_token.wait()
