from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from lahja import EndpointAPI

from eth.chains.mainnet import (
    PETERSBURG_MAINNET_BLOCK,
)
from eth.chains.ropsten import (
    PETERSBURG_ROPSTEN_BLOCK,
)

from trinity._utils.shutdown import exit_with_services
from trinity.config import (
    Eth1AppConfig,
)
from trinity.constants import (
    SYNC_LIGHT,
    TO_NETWORKING_BROADCAST_CONFIG,
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity.db.manager import DBClient
from trinity.extensibility import (
    AsyncioIsolatedComponent,
)
from trinity.components.builtin.tx_pool.pool import (
    TxPool,
)
from trinity.components.builtin.tx_pool.validators import (
    DefaultTransactionValidator
)
from trinity.protocol.eth.peer import ETHProxyPeerPool


class TxComponent(AsyncioIsolatedComponent):
    tx_pool: TxPool = None

    @property
    def name(self) -> str:
        return "TxComponent"

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-tx-pool",
            action="store_true",
            help="Disables the Transaction Pool",
        )

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:

        light_mode = self.boot_info.args.sync_mode == SYNC_LIGHT
        is_disable = self.boot_info.args.disable_tx_pool
        is_supported = not light_mode
        is_enabled = not is_disable and is_supported

        if is_disable:
            self.logger.info("Transaction pool disabled")
        elif not is_supported:
            self.logger.warning("Transaction pool disabled.  Not supported in light mode.")
        elif is_enabled:
            self.start()
        else:
            raise Exception("This code path should be unreachable")

    def do_start(self) -> None:

        trinity_config = self.boot_info.trinity_config
        db = DBClient.connect(trinity_config.database_ipc_path)

        app_config = trinity_config.get_app_config(Eth1AppConfig)
        chain_config = app_config.get_chain_config()

        chain = chain_config.full_chain_class(db)

        if self.boot_info.trinity_config.network_id == MAINNET_NETWORK_ID:
            validator = DefaultTransactionValidator(chain, PETERSBURG_MAINNET_BLOCK)
        elif self.boot_info.trinity_config.network_id == ROPSTEN_NETWORK_ID:
            validator = DefaultTransactionValidator(chain, PETERSBURG_ROPSTEN_BLOCK)
        else:
            raise ValueError("The TxPool component only supports MainnetChain or RopstenChain")

        proxy_peer_pool = ETHProxyPeerPool(self.event_bus, TO_NETWORKING_BROADCAST_CONFIG)

        self.tx_pool = TxPool(self.event_bus, proxy_peer_pool, validator)
        asyncio.ensure_future(exit_with_services(self.tx_pool, self._event_bus_service))
        asyncio.ensure_future(self.tx_pool.run())

    async def do_stop(self) -> None:
        # This isn't really needed for the standard shutdown case as the TxPool will automatically
        # shutdown whenever the `CancelToken` it was chained with is triggered. It may still be
        # useful to stop the TxPool component individually though.
        if self.tx_pool.is_operational:
            await self.tx_pool.cancel()
            self.logger.info("Successfully stopped TxPool")
