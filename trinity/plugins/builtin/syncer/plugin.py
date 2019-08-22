from abc import (
    ABC,
    abstractmethod,
)
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import asyncio
from logging import (
    Logger,
)
from multiprocessing.managers import (
    BaseManager,
)
from typing import (
    cast,
    Iterable,
    Type,
)

from lahja import EndpointAPI

from cancel_token import CancelToken
from eth.abc import (
    AtomicDatabaseAPI,
    ChainAPI,
)
from eth_utils import (
    to_tuple,
    ValidationError,
)

from trinity.config import (
    Eth1AppConfig,
)
from trinity.constants import (
    NETWORKING_EVENTBUS_ENDPOINT,
    SYNC_FAST,
    SYNC_FULL,
    SYNC_LIGHT,
    SYNC_BEAM,
)
from trinity.db.eth1.chain import AsyncChainDB
from trinity.db.eth1.header import AsyncHeaderDB
from trinity.extensibility.asyncio import (
    AsyncioIsolatedPlugin
)
from trinity.nodes.base import (
    Node,
)
from trinity.events import ShutdownRequest
from trinity.protocol.common.peer import (
    BasePeer,
    BasePeerPool,
)
from trinity.protocol.eth.peer import (
    BaseChainPeerPool,
    ETHPeerPool,
)
from trinity.protocol.les.peer import (
    LESPeerPool,
)
from trinity.sync.full.service import (
    FastThenFullChainSyncer,
    FullChainSyncer,
)
from trinity.sync.beam.service import (
    BeamSyncService,
)
from trinity.sync.light.chain import (
    LightChainSyncer,
)
from trinity._utils.shutdown import (
    exit_with_services,
)
from .cli import NormalizeCheckpointURI


class BaseSyncStrategy(ABC):

    @property
    def shutdown_node_on_halt(self) -> bool:
        """
        Return ``False`` if the `sync` is allowed to complete without causing
        the node to fully shut down.
        """
        return True

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser) -> None:
        """
        Configure the argument parser for the specific sync strategy.
        """
        pass

    @classmethod
    @abstractmethod
    def get_sync_mode(cls) -> str:
        ...

    @abstractmethod
    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:
        ...


class NoopSyncStrategy(BaseSyncStrategy):

    @property
    def shutdown_node_on_halt(self) -> bool:
        return False

    @classmethod
    def get_sync_mode(cls) -> str:
        return 'none'

    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:

        logger.info("Node running without sync (--sync-mode=%s)", self.get_sync_mode())


class FullSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_FULL

    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:

        syncer = FullChainSyncer(
            chain,
            AsyncChainDB(base_db),
            base_db,
            cast(ETHPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class FastThenFullSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_FAST

    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:

        syncer = FastThenFullChainSyncer(
            chain,
            AsyncChainDB(base_db),
            base_db,
            cast(ETHPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class BeamSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_BEAM

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser) -> None:
        arg_parser.add_argument(
            '--force-beam-block-number',
            type=int,
            help="Force beam sync to activate on a specific block number (for testing)",
            default=None,
        )

        arg_parser.add_argument(
            '--beam-from-checkpoint',
            action=NormalizeCheckpointURI,
            help=(
                "Start beam sync from a trusted checkpoint specified using URI syntax:"
                "By specific block, eth://block/byhash/<hash>?score=<score>"
                "Let etherscan pick a block near the tip, eth://block/byetherscan/latest"
            ),
            default=None,
        )

    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:

        syncer = BeamSyncService(
            chain,
            AsyncChainDB(base_db),
            base_db,
            cast(ETHPeerPool, peer_pool),
            event_bus,
            args.beam_from_checkpoint,
            args.force_beam_block_number,
            cancel_token,
        )

        await syncer.run()


class LightSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_LIGHT

    async def sync(self,
                   args: Namespace,
                   logger: Logger,
                   chain: ChainAPI,
                   base_db: AtomicDatabaseAPI,
                   peer_pool: BasePeerPool,
                   event_bus: EndpointAPI,
                   cancel_token: CancelToken) -> None:

        syncer = LightChainSyncer(
            chain,
            AsyncHeaderDB(base_db),
            cast(LESPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class SyncerPlugin(AsyncioIsolatedPlugin):
    peer_pool: BaseChainPeerPool = None
    cancel_token: CancelToken = None
    chain: ChainAPI = None
    db_manager: BaseManager = None

    active_strategy: BaseSyncStrategy = None
    strategies: Iterable[BaseSyncStrategy] = (
        FastThenFullSyncStrategy(),
        FullSyncStrategy(),
        BeamSyncStrategy(),
        LightSyncStrategy(),
        NoopSyncStrategy(),
    )

    default_strategy = FastThenFullSyncStrategy

    @property
    def name(self) -> str:
        return "Sync / PeerPool"

    @property
    def normalized_name(self) -> str:
        return NETWORKING_EVENTBUS_ENDPOINT

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        if cls.default_strategy not in cls.extract_strategy_types():
            raise ValidationError(f"Default strategy {cls.default_strategy} not in strategies")

        for sync_strategy in cls.strategies:
            sync_strategy.configure_parser(arg_parser)

        syncing_parser = arg_parser.add_argument_group('sync mode')
        mode_parser = syncing_parser.add_mutually_exclusive_group()
        mode_parser.add_argument(
            '--sync-mode',
            choices=cls.extract_modes(),
            default=cls.default_strategy.get_sync_mode(),
        )

    @classmethod
    @to_tuple
    def extract_modes(cls) -> Iterable[str]:
        for strategy in cls.strategies:
            yield strategy.get_sync_mode()

    @classmethod
    @to_tuple
    def extract_strategy_types(cls) -> Iterable[Type[BaseSyncStrategy]]:
        for strategy in cls.strategies:
            yield type(strategy)

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        for strategy in self.strategies:
            if strategy.get_sync_mode().lower() == self.boot_info.args.sync_mode.lower():
                if self.active_strategy is not None:
                    raise ValidationError(
                        f"Ambiguous sync strategy. Both {self.active_strategy} and {strategy} apply"
                    )
                self.active_strategy = strategy

        if not self.active_strategy:
            self.logger.warn(
                "No sync strategy matches --sync-mode=%s",
                self.boot_info.args.sync_mode
            )
            return

        self.start()

    def do_start(self) -> None:

        trinity_config = self.boot_info.trinity_config
        NodeClass = trinity_config.get_app_config(Eth1AppConfig).node_class
        node = NodeClass(self.event_bus, trinity_config)

        asyncio.ensure_future(self.launch_sync(node))

        asyncio.ensure_future(exit_with_services(
            node,
            self._event_bus_service,
        ))
        asyncio.ensure_future(node.run())

    async def launch_sync(self, node: Node[BasePeer]) -> None:
        await node.events.started.wait()
        await self.active_strategy.sync(
            self.boot_info.args,
            self.logger,
            node.get_chain(),
            node.base_db,
            node.get_peer_pool(),
            self.event_bus,
            node.cancel_token
        )

        if self.active_strategy.shutdown_node_on_halt:
            self.logger.error("Sync ended unexpectedly. Shutting down trinity")
            await self.event_bus.broadcast(ShutdownRequest("Sync ended unexpectedly"))
