from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from eth.chains.mainnet import (
    BYZANTIUM_MAINNET_BLOCK,
)
from eth.chains.ropsten import (
    BYZANTIUM_ROPSTEN_BLOCK,
)

from trinity.config import (
    Eth1AppConfig,
)
from trinity.constants import (
    SYNC_LIGHT,
    TO_NETWORKING_BROADCAST_CONFIG,
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity.db.eth1.manager import (
    create_db_consumer_manager
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.plugins.builtin.tx_pool.pool import (
    TxPool,
)
from trinity.plugins.builtin.tx_pool.validators import (
    DefaultTransactionValidator
)
from trinity.protocol.eth.peer import ETHProxyPeerPool


class TxPlugin(AsyncioIsolatedPlugin):
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
        is_enabled = self.boot_info.args.tx_pool and not light_mode

        unsupported = self.boot_info.args.tx_pool and light_mode

        if is_enabled and not unsupported:
            self.start()
        elif unsupported:
            unsupported_msg = "Transaction pool not available in light mode"
            self.logger.error(unsupported_msg)
            manager_eventbus.request_shutdown(unsupported_msg)

    def do_start(self) -> None:

        trinity_config = self.boot_info.trinity_config
        db_manager = create_db_consumer_manager(trinity_config.database_ipc_path)
        db = db_manager.get_db()  # type: ignore

        app_config = trinity_config.get_app_config(Eth1AppConfig)
        chain_config = app_config.get_chain_config()

        chain = chain_config.full_chain_class(db)

        if self.boot_info.trinity_config.network_id == MAINNET_NETWORK_ID:
            validator = DefaultTransactionValidator(chain, BYZANTIUM_MAINNET_BLOCK)
        elif self.boot_info.trinity_config.network_id == ROPSTEN_NETWORK_ID:
            validator = DefaultTransactionValidator(chain, BYZANTIUM_ROPSTEN_BLOCK)
        else:
            # TODO: We could hint the user about e.g. a --tx-pool-no-validation flag to run the
            # tx pool without tx validation in this case
            raise ValueError("The TxPool plugin only supports MainnetChain or RopstenChain")

        proxy_peer_pool = ETHProxyPeerPool(self.event_bus, TO_NETWORKING_BROADCAST_CONFIG)

        self.tx_pool = TxPool(self.event_bus, proxy_peer_pool, validator)
        asyncio.ensure_future(self.tx_pool.run())

    async def do_stop(self) -> None:
        # This isn't really needed for the standard shutdown case as the TxPool will automatically
        # shutdown whenever the `CancelToken` it was chained with is triggered. It may still be
        # useful to stop the TxPool plugin individually though.
        if self.tx_pool.is_operational:
            await self.tx_pool.cancel()
            self.logger.info("Successfully stopped TxPool")
