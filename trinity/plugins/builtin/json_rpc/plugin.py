from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

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


class JsonRpcServerPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "JSON-RPC Server"

    def on_ready(self) -> None:
        if not self.context.args.disable_rpc:
            self.start()

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-rpc",
            action="store_true",
            help="Disables the JSON-RPC Server",
        )

    def do_start(self) -> None:
        db_manager = create_db_manager(self.context.trinity_config.database_ipc_path)
        db_manager.connect()

        trinity_config = self.context.trinity_config
        chain_config = trinity_config.get_chain_config()

        chain: BaseAsyncChain

        if self.context.trinity_config.is_light_mode:
            header_db = db_manager.get_headerdb()  # type: ignore
            event_bus_light_peer_chain = EventBusLightPeerChain(self.context.event_bus)
            chain = chain_config.light_chain_class(header_db, peer_chain=event_bus_light_peer_chain)
        elif trinity_config.is_full_mode:
            db = db_manager.get_db()  # type: ignore
            chain = chain_config.full_chain_class(db)
        else:
            raise NotImplementedError(f"Unsupported mode: {trinity_config.sync_mode}")

        rpc = RPCServer(chain, self.context.event_bus)
        ipc_server = IPCServer(rpc, self.context.trinity_config.jsonrpc_ipc_path)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_with_service_and_endpoint(ipc_server, self.context.event_bus))
        asyncio.ensure_future(ipc_server.run())
        loop.run_forever()
        loop.close()
