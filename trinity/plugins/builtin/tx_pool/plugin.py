from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from cancel_token import CancelToken

from eth.chains.base import (
    BaseChain
)
from eth.chains.mainnet import (
    BYZANTIUM_MAINNET_BLOCK,
    BaseMainnetChain,
)
from eth.chains.ropsten import (
    BYZANTIUM_ROPSTEN_BLOCK,
    BaseRopstenChain,
)

from p2p.peer import (
    PeerPool
)

from trinity.constants import (
    SYNC_LIGHT
)
from trinity.extensibility import (
    BaseEvent,
    BasePlugin,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent,
    TrinityStartupEvent,
)
from trinity.plugins.builtin.tx_pool.pool import (
    TxPool,
)
from trinity.plugins.builtin.tx_pool.validators import (
    DefaultTransactionValidator
)


class TxPlugin(BasePlugin):

    def __init__(self) -> None:
        self.peer_pool: PeerPool = None
        self.cancel_token: CancelToken = None
        self.chain: BaseChain = None
        self.is_enabled: bool = False

    @property
    def name(self) -> str:
        return "TxPlugin"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--tx-pool",
            action="store_true",
            help="Enables the Transaction Pool (experimental)",
        )

    def handle_event(self, activation_event: BaseEvent) -> None:
        if isinstance(activation_event, TrinityStartupEvent):
            light_mode = activation_event.args.sync_mode == SYNC_LIGHT
            self.is_enabled = activation_event.args.tx_pool and not light_mode
            if activation_event.args.tx_pool and light_mode:
                self.logger.error('The transaction pool is not yet available in light mode')
                self.context.shutdown_host()
        if isinstance(activation_event, ResourceAvailableEvent):
            if activation_event.resource_type is PeerPool:
                self.peer_pool, self.cancel_token = activation_event.resource
            elif activation_event.resource_type is BaseChain:
                self.chain = activation_event.resource

    def should_start(self) -> bool:
        return all((self.peer_pool is not None, self.chain is not None, self.is_enabled))

    def start(self) -> None:
        if isinstance(self.chain, BaseMainnetChain):
            validator = DefaultTransactionValidator(self.chain, BYZANTIUM_MAINNET_BLOCK)
        elif isinstance(self.chain, BaseRopstenChain):
            validator = DefaultTransactionValidator(self.chain, BYZANTIUM_ROPSTEN_BLOCK)
        else:
            # TODO: We could hint the user about e.g. a --tx-pool-no-validation flag to run the
            # tx pool without tx validation in this case
            raise ValueError("The TxPool plugin only supports MainnetChain or RopstenChain")

        tx_pool = TxPool(self.peer_pool, validator, self.cancel_token)
        asyncio.ensure_future(tx_pool.run())
