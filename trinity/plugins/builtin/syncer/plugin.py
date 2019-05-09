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

from trinity.constants import (
    SYNC_FAST,
    SYNC_FULL,
    SYNC_LIGHT,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent,
)
from trinity.extensibility.plugin import (
    BaseAsyncStopPlugin,
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
from trinity.sync.light.chain import (
    LightChainSyncer,
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
                   peer_pool: BaseChainPeerPool,
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
                   peer_pool: BaseChainPeerPool,
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
                   peer_pool: BaseChainPeerPool,
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
                   peer_pool: BaseChainPeerPool,
                   cancel_token: CancelToken) -> None:

        syncer = FastThenFullChainSyncer(
            chain,
            db_manager.get_chaindb(),  # type: ignore
            db_manager.get_db(),  # type: ignore
            cast(ETHPeerPool, peer_pool),
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
                   peer_pool: BaseChainPeerPool,
                   cancel_token: CancelToken) -> None:

        syncer = LightChainSyncer(
            chain,
            db_manager.get_headerdb(),  # type: ignore
            cast(LESPeerPool, peer_pool),
            cancel_token,
        )

        await syncer.run()


class SyncerPlugin(BaseAsyncStopPlugin):
    peer_pool: BaseChainPeerPool = None
    cancel_token: CancelToken = None
    chain: BaseChain = None
    db_manager: BaseManager = None

    active_strategy: BaseSyncStrategy = None
    strategies: Iterable[BaseSyncStrategy] = (
        FastThenFullSyncStrategy(),
        FullSyncStrategy(),
        LightSyncStrategy(),
        NoopSyncStrategy(),
    )

    default_strategy = FastThenFullSyncStrategy

    @property
    def name(self) -> str:
        return "Syncer Plugin"

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

        self.event_bus.subscribe(ResourceAvailableEvent, self.handle_event)

    def handle_event(self, event: ResourceAvailableEvent) -> None:

        if self.running:
            return

        if issubclass(event.resource_type, BaseChainPeerPool):
            self.peer_pool, self.cancel_token = event.resource
        elif event.resource_type is BaseManager:
            self.db_manager = event.resource
        elif event.resource_type is BaseChain:
            self.chain = event.resource

        if None not in (self.peer_pool, self.db_manager, self.chain):
            self.start()

    def do_start(self) -> None:
        asyncio.ensure_future(self.handle_sync())

    async def handle_sync(self) -> None:
        await self.active_strategy.sync(
            self.logger,
            self.chain,
            self.db_manager,
            self.peer_pool,
            self.cancel_token
        )

        if self.active_strategy.shutdown_node_on_halt:
            self.logger.error("Sync ended unexpectedly. Shutting down trinity")
            self.event_bus.request_shutdown("Sync ended unexpectedly")
