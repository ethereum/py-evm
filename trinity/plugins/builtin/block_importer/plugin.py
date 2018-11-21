from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from trinity.db.manager import (
    create_db_manager
)
from trinity.extensibility import (
    BaseIsolatedPlugin,
)
from trinity.plugins.builtin.block_importer import (
    BlockImportHandler,
)
from trinity.utils.shutdown import (
    exit_with_service_and_endpoint,
)


class BlockImporterPlugin(BaseIsolatedPlugin):
    """
    FILL IN
    """

    @property
    def name(self) -> str:
        return "Block Importer"

    def on_ready(self) -> None:
        if not self.context.args.disable_block_importer:
            self.start()

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-block-importer",
            action="store_true",
            help="Disable the Block Importer",
        )

    def do_start(self) -> None:
        db_manager = create_db_manager(self.context.trinity_config.database_ipc_path)
        db_manager.connect()

        trinity_config = self.context.trinity_config
        chain_config = trinity_config.get_chain_config()

        # TODO: Double check what we need for light mode sync
        db = db_manager.get_db()  # type: ignore
        chain = chain_config.full_chain_class(db)

        handler = BlockImportHandler(chain, self.event_bus)

        loop = asyncio.get_event_loop()
        asyncio.ensure_future(exit_with_service_and_endpoint(handler, self.event_bus))
        asyncio.ensure_future(handler.run())
        loop.run_forever()
        loop.close()
