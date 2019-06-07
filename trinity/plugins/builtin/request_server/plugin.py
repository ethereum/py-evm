from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
from multiprocessing.managers import (
    BaseManager,
)
import asyncio

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
from trinity.db.eth1.manager import (
    create_db_consumer_manager,
)
from trinity.db.beacon.manager import (
    create_db_consumer_manager as create_beacon_db_consumer_manager,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.protocol.bcc.servers import (
    BCCRequestServer,
)
from trinity.protocol.eth.servers import (
    ETHRequestServer
)
from trinity.protocol.les.servers import (
    LightRequestServer,
)
from trinity._utils.shutdown import (
    exit_with_endpoint_and_services,
)


class RequestServerPlugin(AsyncioIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Request Server"

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
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

        if trinity_config.has_app_config(Eth1AppConfig):
            db_manager = create_db_consumer_manager(trinity_config.database_ipc_path)
            server = self.make_eth1_request_server(
                trinity_config.get_app_config(Eth1AppConfig),
                db_manager,
            )
        elif trinity_config.has_app_config(BeaconAppConfig):
            db_manager = create_beacon_db_consumer_manager(trinity_config.database_ipc_path)
            server = self.make_beacon_request_server(
                trinity_config.get_app_config(BeaconAppConfig),
                db_manager,
            )
        else:
            raise Exception("Trinity config must have either eth1 or beacon chain config")

        asyncio.ensure_future(exit_with_endpoint_and_services(self.event_bus, server))
        asyncio.ensure_future(server.run())

    def make_eth1_request_server(self,
                                 app_config: Eth1AppConfig,
                                 db_manager: BaseManager) -> BaseService:

        if app_config.database_mode is Eth1DbMode.LIGHT:
            header_db = db_manager.get_headerdb()  # type: ignore
            server: BaseService = LightRequestServer(
                self.event_bus,
                TO_NETWORKING_BROADCAST_CONFIG,
                header_db
            )
        elif app_config.database_mode is Eth1DbMode.FULL:
            chain_db = db_manager.get_chaindb()  # type: ignore
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
                                   db_manager: BaseManager) -> BaseService:

        return BCCRequestServer(
            self.event_bus,
            TO_NETWORKING_BROADCAST_CONFIG,
            db_manager.get_chaindb()  # type: ignore
        )
