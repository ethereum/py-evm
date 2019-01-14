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
    SYNC_LIGHT,
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
    FullNodeSyncer,
)
from trinity.sync.light.chain import (
    LightChainSyncer,
)


class BaseSyncStrategy(ABC):

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

        syncer = FullNodeSyncer(
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
    strategies: Iterable[BaseSyncStrategy]

    def __init__(self,
                 strategies: Iterable[BaseSyncStrategy],
                 default_strategy: Type[BaseSyncStrategy]):
        # Other plugins can get a reference to this plugin instance and
        # add another sync strategy which will then be available under --sync-strategy=<other>
        self.strategies = strategies
        self.default_strategy = default_strategy

    @property
    def name(self) -> str:
        return "Syncer Plugin"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        if self.default_strategy not in self.extract_strategy_types():
            raise ValidationError(f"Default strategy {self.default_strategy} not in strategies")

        syncing_parser = arg_parser.add_argument_group('sync mode')
        mode_parser = syncing_parser.add_mutually_exclusive_group()
        mode_parser.add_argument(
            '--sync-mode',
            choices=self.extract_modes(),
            default=self.default_strategy.get_sync_mode(),
        )

    @to_tuple
    def extract_modes(self) -> Iterable[str]:
        for strategy in self.strategies:
            yield strategy.get_sync_mode()

    @to_tuple
    def extract_strategy_types(self) -> Iterable[Type[BaseSyncStrategy]]:
        for strategy in self.strategies:
            yield type(strategy)

    def on_ready(self) -> None:
        for strategy in self.strategies:
            if strategy.get_sync_mode().lower() == self.context.args.sync_mode.lower():
                if self.active_strategy is not None:
                    raise ValidationError(
                        f"Ambiguous sync strategy. Both {self.active_strategy} and {strategy} apply"
                    )
                self.active_strategy = strategy

        if not self.active_strategy:
            self.logger.warn("No sync strategy matches --sync-mode=%s", self.context.args.sync_mode)
            return

        self.event_bus.subscribe(ResourceAvailableEvent, self.handle_event)

    def handle_event(self, event: ResourceAvailableEvent) -> None:
        if issubclass(event.resource_type, BaseChainPeerPool):
            self.peer_pool, self.cancel_token = event.resource
        elif event.resource_type is BaseManager:
            self.db_manager = event.resource
        elif event.resource_type is BaseChain:
            self.chain = event.resource

        if None not in (self.peer_pool, self.db_manager, self.chain):
            self.start()

    def do_start(self) -> None:
        asyncio.ensure_future(
            self.active_strategy.sync(
                self.logger,
                self.chain,
                self.db_manager,
                self.peer_pool,
                self.cancel_token
            )
        )
