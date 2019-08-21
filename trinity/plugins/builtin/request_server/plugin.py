from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from lahja import EndpointAPI

from eth.db.backends.base import BaseAtomicDB

from p2p.service import (
    BaseService,
)

from trinity.config import (
    BeaconAppConfig,
    Eth1AppConfig,
    Eth1DbMode,
)
from trinity.constants import (
    TO_NETWORKING_BROADCAST_CONFIG,
)
from trinity.db.manager import DBClient
from trinity.db.eth1.chain import AsyncChainDB
from trinity.db.eth1.header import AsyncHeaderDB
from trinity.db.beacon.chain import AsyncBeaconChainDB
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.protocol.bcc.servers import BCCRequestServer
from trinity.protocol.eth.servers import ETHRequestServer
from trinity.protocol.les.servers import LightRequestServer
from trinity._utils.shutdown import exit_with_services


class RequestServerPlugin(AsyncioIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Request Server"

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        if not self.boot_info.args.disable_request_server:
            self.start()

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-request-server",
            action="store_true",
            help="Disables the Request Server",
        )

    def do_start(self) -> None:

        trinity_config = self.boot_info.trinity_config
        base_db = DBClient.connect(trinity_config.database_ipc_path)

        if trinity_config.has_app_config(Eth1AppConfig):
            server = self.make_eth1_request_server(
                trinity_config.get_app_config(Eth1AppConfig),
                base_db,
            )
        elif trinity_config.has_app_config(BeaconAppConfig):
            server = self.make_beacon_request_server(
                trinity_config.get_app_config(BeaconAppConfig),
                base_db,
            )
        else:
            raise Exception("Trinity config must have either eth1 or beacon chain config")

        asyncio.ensure_future(exit_with_services(server, self._event_bus_service))
        asyncio.ensure_future(server.run())

    def make_eth1_request_server(self,
                                 app_config: Eth1AppConfig,
                                 base_db: BaseAtomicDB) -> BaseService:

        if app_config.database_mode is Eth1DbMode.LIGHT:
            header_db = AsyncHeaderDB(base_db)
            server: BaseService = LightRequestServer(
                self.event_bus,
                TO_NETWORKING_BROADCAST_CONFIG,
                header_db
            )
        elif app_config.database_mode is Eth1DbMode.FULL:
            chain_db = AsyncChainDB(base_db)
            server = ETHRequestServer(
                self.event_bus,
                TO_NETWORKING_BROADCAST_CONFIG,
                chain_db
            )
        else:
            raise Exception(f"Unsupported Database Mode: {app_config.database_mode}")

        return server

    def make_beacon_request_server(self,
                                   app_config: BeaconAppConfig,
                                   base_db: BaseAtomicDB) -> BaseService:

        return BCCRequestServer(
            self.event_bus,
            TO_NETWORKING_BROADCAST_CONFIG,
            AsyncBeaconChainDB(base_db, app_config.get_chain_config().genesis_config),
        )
