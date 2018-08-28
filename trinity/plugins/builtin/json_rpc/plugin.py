from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from cancel_token import (
    CancelToken
)

from eth.chains.base import (
    BaseChain
)

from p2p.peer import (
    PeerPool
)

from trinity.constants import (
    SYNC_LIGHT
)
from trinity.extensibility import (
    BaseEvent,
    BaseIsolatedPlugin,
    BasePlugin,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent
)
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.db_proxy import (
    create_db_manager
)
from trinity.utils.shutdown import (
    exit_on_signal
)


class JsonRpcServerPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "JSON-RPC Server"

    def should_start(self) -> bool:
        return not self.context.args.disable_rpc and not self.context.args.sync_mode == SYNC_LIGHT

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-rpc",
            action="store_true",
            help="Disables the JSON-RPC Server",
        )

    def start(self) -> None:
        self.logger.info('JSON-RPC Server started')
        self.context.event_bus.connect()

        db_manager = create_db_manager(self.context.chain_config.database_ipc_path)
        db_manager.connect()

        chain_class = self.context.chain_config.node_class.chain_class
        db = db_manager.get_db()  # type: ignore
        chain = chain_class(db)

        rpc = RPCServer(chain, self.context.event_bus)
        ipc_server = IPCServer(rpc, self.context.chain_config.jsonrpc_ipc_path)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_on_signal(ipc_server, self.context.event_bus))
        asyncio.ensure_future(ipc_server.run())
        loop.run_forever()
        loop.close()


class JsonRpcServerLightPlugin(BasePlugin):
    """
    The ``JsonRpcServerLightPlugin`` is an intermediate step to keep the
    JSON-RPC server inside the networking process when in ``light`` mode.
    This is because in ``light`` mode, the chain is more coupled to the
    ``PeerPool``. This should move when the ``PeerPool`` becomes more
    multiprocess friendly, exposing events and APIs via event bus.
    """

    def __init__(self) -> None:
        super().__init__()
        self.peer_pool: PeerPool = None
        self.cancel_token: CancelToken = None
        self.chain: BaseChain = None

    @property
    def name(self) -> str:
        return "JSON-RPC Server Light"

    def should_start(self) -> bool:
        return all((self.peer_pool is not None,
                    self.chain is not None,
                    not self.context.args.disable_rpc,
                    self.context.args.sync_mode == SYNC_LIGHT))

    def handle_event(self, activation_event: BaseEvent) -> None:
        if isinstance(activation_event, ResourceAvailableEvent):
            if activation_event.resource_type is PeerPool:
                self.peer_pool, self.cancel_token = activation_event.resource
            elif activation_event.resource_type is BaseChain:
                self.chain = activation_event.resource

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        # The JsonRpcServerPlugin plugin above already configures the --disable-rpc flag
        pass

    def start(self) -> None:
        self.logger.info('JSON-RPC Server started')

        rpc = RPCServer(self.chain, self.context.event_bus)
        # The IPCServer used to have its own event loop because a comment indicated
        # it may otherwise run into deadlocks. Not sure yet what to do about that
        # because having two distinct event loops seems to be problematic now that
        # the RPCServer uses the eventbus to retrieve the peer count
        ipc = IPCServer(rpc, self.context.chain_config.jsonrpc_ipc_path)
        asyncio.ensure_future(ipc.run())
