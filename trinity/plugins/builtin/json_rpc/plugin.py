from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from lahja import EndpointAPI

from eth.db.header import (
    HeaderDB,
)

from trinity.config import (
    Eth1AppConfig,
    Eth1DbMode,
    BeaconAppConfig,
    TrinityConfig
)
from trinity.chains.base import AsyncChainAPI
from trinity.chains.light_eventbus import (
    EventBusLightPeerChain,
)
from trinity.db.manager import DBClient
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.modules import (
    initialize_beacon_modules,
    initialize_eth1_modules,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity._utils.shutdown import (
    exit_with_services,
)


class JsonRpcServerPlugin(AsyncioIsolatedPlugin):

    @property
    def name(self) -> str:
        return "JSON-RPC API"

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        if not self.boot_info.args.disable_rpc:
            self.start()

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-rpc",
            action="store_true",
            help="Disables the JSON-RPC Server",
        )

    def chain_for_eth1_config(self, trinity_config: TrinityConfig,
                              eth1_app_config: Eth1AppConfig) -> AsyncChainAPI:
        chain_config = eth1_app_config.get_chain_config()

        db = DBClient.connect(trinity_config.database_ipc_path)

        if eth1_app_config.database_mode is Eth1DbMode.LIGHT:
            header_db = HeaderDB(db)
            event_bus_light_peer_chain = EventBusLightPeerChain(self.event_bus)
            return chain_config.light_chain_class(
                header_db, peer_chain=event_bus_light_peer_chain
            )
        elif eth1_app_config.database_mode is Eth1DbMode.FULL:
            return chain_config.full_chain_class(db)
        else:
            raise Exception(f"Unsupported Database Mode: {eth1_app_config.database_mode}")

    def chain_for_config(self, trinity_config: TrinityConfig) -> AsyncChainAPI:
        if trinity_config.has_app_config(BeaconAppConfig):
            return None
        elif trinity_config.has_app_config(Eth1AppConfig):
            eth1_app_config = trinity_config.get_app_config(Eth1AppConfig)
            return self.chain_for_eth1_config(trinity_config, eth1_app_config)
        else:
            raise Exception("Unsupported Node Type")

    def do_start(self) -> None:
        trinity_config = self.boot_info.trinity_config
        chain = self.chain_for_config(trinity_config)

        if trinity_config.has_app_config(Eth1AppConfig):
            modules = initialize_eth1_modules(chain, self.event_bus)
        elif trinity_config.has_app_config(BeaconAppConfig):
            modules = initialize_beacon_modules(chain, self.event_bus)
        else:
            raise Exception("Unsupported Node Type")

        rpc = RPCServer(modules, chain, self.event_bus)
        ipc_server = IPCServer(rpc, self.boot_info.trinity_config.jsonrpc_ipc_path)

        asyncio.ensure_future(exit_with_services(
            ipc_server,
            self._event_bus_service,
        ))
        asyncio.ensure_future(ipc_server.run())
