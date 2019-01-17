from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio
from typing import (
    Tuple
)

from trinity.config import (
    Eth1AppConfig,
    Eth1DbMode,
    BeaconAppConfig,
    TrinityConfig
)
from trinity.chains.base import BaseAsyncChain
from trinity.db.eth1.manager import (
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
from trinity.rpc.modules import (
    BeaconChainRPCModule,
    initialize_beacon_modules,
    initialize_eth1_modules,
    Eth1ChainRPCModule,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity._utils.shutdown import (
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

    def setup_eth1_modules(self, trinity_config: TrinityConfig) -> Tuple[Eth1ChainRPCModule, ...]:
        db_manager = create_db_manager(trinity_config.database_ipc_path)
        db_manager.connect()

        eth1_app_config = trinity_config.get_app_config(Eth1AppConfig)
        chain_config = trinity_config.get_chain_config()

        chain: BaseAsyncChain

        if eth1_app_config.database_mode is Eth1DbMode.LIGHT:
            header_db = db_manager.get_headerdb()  # type: ignore
            event_bus_light_peer_chain = EventBusLightPeerChain(self.context.event_bus)
            chain = chain_config.light_chain_class(header_db, peer_chain=event_bus_light_peer_chain)
        elif eth1_app_config.database_mode is Eth1DbMode.FULL:
            db = db_manager.get_db()  # type: ignore
            chain = chain_config.full_chain_class(db)
        else:
            raise Exception(f"Unsupported Database Mode: {eth1_app_config.database_mode}")

        return initialize_eth1_modules(chain, self.event_bus)

    def setup_beacon_modules(self) -> Tuple[BeaconChainRPCModule, ...]:

        return initialize_beacon_modules(None, self.event_bus)

    def do_start(self) -> None:

        trinity_config = self.context.trinity_config

        if trinity_config.has_app_config(Eth1AppConfig):
            modules = self.setup_eth1_modules(trinity_config)
        elif trinity_config.has_app_config(BeaconAppConfig):
            modules = self.setup_beacon_modules()
        else:
            raise Exception("Unsupported Node Type")

        rpc = RPCServer(modules, self.context.event_bus)
        ipc_server = IPCServer(rpc, self.context.trinity_config.jsonrpc_ipc_path)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_with_service_and_endpoint(ipc_server, self.context.event_bus))
        asyncio.ensure_future(ipc_server.run())
        loop.run_forever()
        loop.close()
