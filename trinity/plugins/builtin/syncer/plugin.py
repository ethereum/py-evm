from abc import (
    ABC,
    abstractmethod,
)
from argparse import (
    ArgumentParser,
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

from cancel_token import CancelToken
from eth.chains.base import (
    BaseChain
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
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.asyncio import (
    AsyncioIsolatedPlugin
)
from trinity.nodes.base import (
    Node,
)
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
    exit_with_endpoint_and_services,
)


class BaseSyncStrategy(ABC):

    @property
    def shutdown_node_on_halt(self) -> bool:
        """
        Return ``False`` if the `sync` is allowed to complete without causing
        the node to fully shut down.
        """
        return True

    @classmethod
    @abstractmethod
    def get_sync_mode(cls) -> str:
        pass

    @abstractmethod
    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:
        pass


class NoopSyncStrategy(BaseSyncStrategy):

    @property
    def shutdown_node_on_halt(self) -> bool:
        return False

    @classmethod
    def get_sync_mode(cls) -> str:
        return 'none'

    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:

        logger.info("Node running without sync (--sync-mode=%s)", self.get_sync_mode())


class FullSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_FULL

    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:

        syncer = FullChainSyncer(
            chain,
            db_manager.get_chaindb(),  # type: ignore
            db_manager.get_db(),  # type: ignore
            cast(ETHPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class FastThenFullSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_FAST

    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:

        syncer = FastThenFullChainSyncer(
            chain,
            db_manager.get_chaindb(),  # type: ignore
            db_manager.get_db(),  # type: ignore
            cast(ETHPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class BeamSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_BEAM

    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:

        syncer = BeamSyncService(
            chain,
            db_manager.get_chaindb(),  # type: ignore
            db_manager.get_db(),  # type: ignore
            cast(ETHPeerPool, peer_pool),
            event_bus,
            cancel_token,
        )

        await syncer.run()


class LightSyncStrategy(BaseSyncStrategy):

    @classmethod
    def get_sync_mode(cls) -> str:
        return SYNC_LIGHT

    async def sync(self,
                   logger: Logger,
                   chain: BaseChain,
                   db_manager: BaseManager,
                   peer_pool: BasePeerPool,
                   event_bus: TrinityEventBusEndpoint,
                   cancel_token: CancelToken) -> None:

        syncer = LightChainSyncer(
            chain,
            db_manager.get_headerdb(),  # type: ignore
            cast(LESPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class SyncerPlugin(AsyncioIsolatedPlugin):
    peer_pool: BaseChainPeerPool = None
    cancel_token: CancelToken = None
    chain: BaseChain = None
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

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
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

        asyncio.ensure_future(exit_with_endpoint_and_services(self.event_bus, node))
        asyncio.ensure_future(node.run())

    async def launch_sync(self, node: Node[BasePeer]) -> None:
        await node.events.started.wait()
        await self.active_strategy.sync(
            self.logger,
            node.get_chain(),
            node.db_manager,
            node.get_peer_pool(),
            self.event_bus,
            node.cancel_token
        )

        if self.active_strategy.shutdown_node_on_halt:
            self.logger.error("Sync ended unexpectedly. Shutting down trinity")
            self.event_bus.request_shutdown("Sync ended unexpectedly")
