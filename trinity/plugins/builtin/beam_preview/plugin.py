import asyncio
from abc import abstractmethod

from lahja import EndpointAPI

from trinity._utils.shutdown import exit_with_services
from trinity.config import (
    Eth1AppConfig,
)
from trinity.constants import (
    SYNC_BEAM,
)
from trinity.db.manager import DBClient
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.sync.beam.importer import (
    make_pausing_beam_chain,
    BlockPreviewServer,
)


class BeamChainPreviewPlugin(AsyncioIsolatedPlugin):
    """
    Subscribe to events that request a block import: ``DoStatelessBlockPreview``.
    On every preview, run through all the transactions, downloading the
    necessary data to execute them with the EVM.

    The beam sync previewer blocks when data is missing, so it's important to run
    in an isolated process.
    """
    _beam_chain = None

    @property
    @abstractmethod
    def shard_num(self) -> int:
        """
        Which shard this particular plugin belongs to. Currently,
        there are always 4 shards, so this number must be one of:
        {0, 1, 2, 3}.
        """
        ...

    @property
    def name(self) -> str:
        return f"Beam Sync Chain Preview {self.shard_num}"

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        if self.boot_info.args.sync_mode.upper() == SYNC_BEAM.upper():
            self.start()

    def do_start(self) -> None:
        trinity_config = self.boot_info.trinity_config
        app_config = trinity_config.get_app_config(Eth1AppConfig)
        chain_config = app_config.get_chain_config()

        base_db = DBClient.connect(trinity_config.database_ipc_path)

        self._beam_chain = make_pausing_beam_chain(
            chain_config.vm_configuration,
            chain_config.chain_id,
            base_db,
            self.event_bus,
            self._loop,
            # these preview executions are lower priority than the primary block import
            urgent=False,
        )

        import_server = BlockPreviewServer(self.event_bus, self._beam_chain, self.shard_num)
        asyncio.ensure_future(exit_with_services(import_server, self._event_bus_service))
        asyncio.ensure_future(import_server.run())


class BeamChainPreviewPlugin0(BeamChainPreviewPlugin):
    shard_num = 0


class BeamChainPreviewPlugin1(BeamChainPreviewPlugin):
    shard_num = 1


class BeamChainPreviewPlugin2(BeamChainPreviewPlugin):
    shard_num = 2


class BeamChainPreviewPlugin3(BeamChainPreviewPlugin):
    shard_num = 3
