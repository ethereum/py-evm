from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio
import time
from typing import (
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
    BroadcastConfig,
    Endpoint,
)
from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.db.manager import (
    create_db_manager
)
from trinity.extensibility import (
    BaseIsolatedPlugin,
)
from trinity.plugins.builtin.light_peer_chain_bridge.light_peer_chain_bridge import (
    EventBusLightPeerChain,
)
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.shutdown import (
    exit_with_service_and_endpoint,
)


class DebugResponse(BaseEvent):

    def __init__(self, timestamp: float) -> None:
        self.timestamp = timestamp


class DebugRequest(BaseRequestResponseEvent[DebugResponse]):

    @staticmethod
    def expected_response_type() -> Type[DebugResponse]:
        return DebugResponse



class DebugHandler(BaseService):

    def __init__(self, event_bus: Endpoint):
        super().__init__()
        self.event_bus = event_bus

    async def _run(self):
        async for event in self.event_bus.stream(DebugRequest):
            self.event_bus.broadcast(
                DebugResponse(time.time()),
                event.broadcast_config()
            )


class DebugRequester(BaseService):

    def __init__(self, event_bus: Endpoint):
        super().__init__()
        self.event_bus = event_bus

    async def _run(self):
        while self.is_operational:
            await asyncio.sleep(0.5)

            try:
                response = await self.wait(
                    self.event_bus.request(DebugRequest()),
                    timeout=0.5
                )
            except TimeoutError:
                self.logger.warning("Timeout: DebugHandler did not answer in time")
            else:
                self.logger.info("Received DebugResponse %d", response.timestamp)


class DebugSenderPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Debug Sender"

    def on_ready(self) -> None:
        if self.context.args.debug_lahja:
            self.start()

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--debug-lahja",
            action="store_true",
            help="Disables the JSON-RPC Server",
        )

    def do_start(self) -> None:

        handler = DebugHandler(self.event_bus)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_with_service_and_endpoint(handler, self.event_bus))
        asyncio.ensure_future(handler.run())
        loop.run_forever()
        loop.close()


class DebugReceiverPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Debug Receiver"

    def on_ready(self) -> None:
        if self.context.args.debug_lahja:
            self.start()

    def do_start(self) -> None:

        handler = DebugRequester(self.event_bus)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_with_service_and_endpoint(handler, self.event_bus))
        asyncio.ensure_future(handler.run())
        loop.run_forever()
        loop.close()
