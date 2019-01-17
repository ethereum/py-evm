from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio
from typing import (
    Type,
)

from eth_typing import (
    BlockNumber,
)
from lahja import (
    Endpoint,
)

from eth.constants import (
    GENESIS_BLOCK_NUMBER
)

from p2p.discovery import (
    get_v5_topic,
    DiscoveryByTopicProtocol,
    DiscoveryProtocol,
    DiscoveryService,
    NoopDiscoveryService,
    PreferredNodeDiscoveryProtocol,
)
from p2p.kademlia import (
    Address,
)
from p2p.protocol import (
    Protocol,
)
from p2p.service import (
    BaseService,
)

from trinity.config import (
    BeaconAppConfig,
    Eth1AppConfig,
    Eth1DbMode,
    TrinityConfig,
)
from trinity.db.eth1.manager import (
    create_db_consumer_manager
)
from trinity.extensibility import (
    BaseIsolatedPlugin,
)
from trinity.protocol.bcc.proto import (
    BCCProtocol,
)
from trinity.protocol.eth.proto import (
    ETHProtocol,
)
from trinity.protocol.les.proto import (
    LESProtocolV2,
)
from trinity._utils.shutdown import (
    exit_with_service_and_endpoint,
)


def get_protocol(trinity_config: TrinityConfig) -> Type[Protocol]:
    # For now DiscoveryByTopicProtocol supports a single topic, so we use the latest
    # version of our supported protocols. Maybe this could be more generic?
    # TODO: This needs to support the beacon protocol when we have a way to
    # check the config, if trinity is being run as a beacon node.

    if trinity_config.has_app_config(BeaconAppConfig):
        return BCCProtocol
    else:
        eth1_config = trinity_config.get_app_config(Eth1AppConfig)
        if eth1_config.database_mode is Eth1DbMode.LIGHT:
            return LESProtocolV2
        else:
            return ETHProtocol


def get_discv5_topic(trinity_config: TrinityConfig, protocol: Type[Protocol]) -> bytes:
    db_manager = create_db_consumer_manager(trinity_config.database_ipc_path)
    db_manager.connect()

    header_db = db_manager.get_headerdb()  # type: ignore
    genesis_hash = header_db.get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER))

    return get_v5_topic(protocol, genesis_hash)


class DiscoveryBootstrapService(BaseService):
    """
    Bootstrap discovery to provide a parent ``CancellationToken``
    """

    def __init__(self,
                 disable_discovery: bool,
                 event_bus: Endpoint,
                 trinity_config: TrinityConfig) -> None:
        super().__init__()
        self.is_discovery_disabled = disable_discovery
        self.event_bus = event_bus
        self.trinity_config = trinity_config

    async def _run(self) -> None:
        external_ip = "0.0.0.0"
        address = Address(external_ip, self.trinity_config.port, self.trinity_config.port)

        if self.trinity_config.use_discv5:
            protocol = get_protocol(self.trinity_config)
            topic = get_discv5_topic(self.trinity_config, protocol)

            discovery_protocol: DiscoveryProtocol = DiscoveryByTopicProtocol(
                topic,
                self.trinity_config.nodekey,
                address,
                self.trinity_config.bootstrap_nodes,
                self.cancel_token,
            )
        else:
            discovery_protocol = PreferredNodeDiscoveryProtocol(
                self.trinity_config.nodekey,
                address,
                self.trinity_config.bootstrap_nodes,
                self.trinity_config.preferred_nodes,
                self.cancel_token,
            )

        if self.is_discovery_disabled:
            discovery_service: BaseService = NoopDiscoveryService(
                self.event_bus,
                self.cancel_token,
            )
        else:
            discovery_service = DiscoveryService(
                discovery_protocol,
                self.trinity_config.port,
                self.event_bus,
                self.cancel_token,
            )

        await discovery_service.run()


class PeerDiscoveryPlugin(BaseIsolatedPlugin):
    """
    Continously discover other Ethereum nodes.
    """

    @property
    def name(self) -> str:
        return "Peer Discovery"

    def on_ready(self) -> None:
        self.start()

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-discovery",
            action="store_true",
            help="Disable peer discovery",
        )

    def do_start(self) -> None:
        loop = asyncio.get_event_loop()
        discovery_bootstrap = DiscoveryBootstrapService(
            self.context.args.disable_discovery,
            self.event_bus,
            self.context.trinity_config
        )
        asyncio.ensure_future(exit_with_service_and_endpoint(discovery_bootstrap, self.event_bus))
        asyncio.ensure_future(discovery_bootstrap.run())
        loop.run_forever()
        loop.close()
