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
)
from eth.chains.ropsten import (
    BYZANTIUM_ROPSTEN_BLOCK,
)

from trinity.constants import (
    SYNC_LIGHT,
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    BaseAsyncStopPlugin,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent,
)
from trinity.plugins.builtin.tx_pool.pool import (
    TxPool,
)
from trinity.plugins.builtin.tx_pool.validators import (
    DefaultTransactionValidator
)
from trinity.protocol.eth.peer import ETHPeerPool


class TxPlugin(BaseAsyncStopPlugin):
    peer_pool: ETHPeerPool = None
    cancel_token: CancelToken = None
    chain: BaseChain = None
    is_enabled: bool = False
    tx_pool: TxPool = None

    @property
    def name(self) -> str:
        return "TxPlugin"

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--tx-pool",
            action="store_true",
            help="Enables the Transaction Pool (experimental)",
        )

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:

        light_mode = self.boot_info.args.sync_mode == SYNC_LIGHT
        self.is_enabled = self.boot_info.args.tx_pool and not light_mode

        unsupported = self.boot_info.args.tx_pool and light_mode

        if unsupported:
            unsupported_msg = "Transaction pool not available in light mode"
            self.logger.error(unsupported_msg)
            manager_eventbus.request_shutdown(unsupported_msg)

        self.event_bus.subscribe(ResourceAvailableEvent, self.handle_event)

    def handle_event(self, event: ResourceAvailableEvent) -> None:

        if self.running:
            return

        if event.resource_type is ETHPeerPool:
            self.peer_pool, self.cancel_token = event.resource
        elif event.resource_type is BaseChain:
            self.chain = event.resource

        if all((self.peer_pool is not None, self.chain is not None, self.is_enabled)):
            self.start()

    def do_start(self) -> None:
        if self.boot_info.trinity_config.network_id == MAINNET_NETWORK_ID:
            validator = DefaultTransactionValidator(self.chain, BYZANTIUM_MAINNET_BLOCK)
        elif self.boot_info.trinity_config.network_id == ROPSTEN_NETWORK_ID:
            validator = DefaultTransactionValidator(self.chain, BYZANTIUM_ROPSTEN_BLOCK)
        else:
            # TODO: We could hint the user about e.g. a --tx-pool-no-validation flag to run the
            # tx pool without tx validation in this case
            raise ValueError("The TxPool plugin only supports MainnetChain or RopstenChain")

        self.tx_pool = TxPool(self.peer_pool, validator, self.cancel_token)
        asyncio.ensure_future(self.tx_pool.run())

    async def do_stop(self) -> None:
        # This isn't really needed for the standard shutdown case as the TxPool will automatically
        # shutdown whenever the `CancelToken` it was chained with is triggered. It may still be
        # useful to stop the TxPool plugin individually though.
        if self.tx_pool.is_operational:
            await self.tx_pool.cancel()
            self.logger.info("Successfully stopped TxPool")
