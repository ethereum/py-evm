from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import pathlib
import rlp

from eth_utils import ValidationError

from eth.abc import ChainAPI
from eth.db.atomic import AtomicDB
from eth.db.backends.level import LevelDB
from eth.exceptions import HeaderNotFound
from eth.vm.forks.frontier.blocks import FrontierBlock
from eth.vm.interrupt import EVMMissingData

from trinity.config import (
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.extensibility import (
    BaseMainProcessComponent,
)
from trinity.initialization import (
    ensure_eth1_dirs,
    initialize_database,
)
from .rlp_decode import decode_all


def get_chain(trinity_config: TrinityConfig) -> ChainAPI:
    app_config = trinity_config.get_app_config(Eth1AppConfig)

    ensure_eth1_dirs(app_config)

    base_db = LevelDB(db_path=app_config.database_dir)
    chain_config = app_config.get_chain_config()
    chain = chain_config.full_chain_class(AtomicDB(base_db))

    initialize_database(chain_config, chain.chaindb, base_db)

    return chain


class ImportBlockComponent(BaseMainProcessComponent):
    """
    Import blocks an RLP encoded file.
    """

    @property
    def name(self) -> str:
        return "Import"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        import_parser = subparser.add_parser(
            'import',
            help='Import blocks from a file (RLP encoded)',
        )

        import_parser.add_argument(
            'file_path',
            type=pathlib.Path,
            help='Specify the file to import from'
        )

        import_parser.set_defaults(func=cls.run_import)

    @classmethod
    def run_import(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        logger = cls.get_logger()

        with open(args.file_path, 'rb') as import_file:
            # This won't handle large files.
            # TODO: Make this stream based: https://github.com/ethereum/trinity/issues/1282
            file_bytes = import_file.read()

        blocks = decode_all(file_bytes, sedes=FrontierBlock)

        logger.info("Importing %s blocks", len(blocks))

        chain = get_chain(trinity_config)

        for block in blocks:
            try:
                chain.import_block(block)
            except (EVMMissingData, ValidationError) as exc:
                logger.error(exc)
                logger.error("Import failed")
            else:
                logger.info("Successfully imported %s", block)


class ExportBlockComponent(BaseMainProcessComponent):
    """
    Export blocks to an RLP encoded file.
    """

    @property
    def name(self) -> str:
        return "Export"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        export_parser = subparser.add_parser(
            'export',
            help='Export blocks to a file (RLP encoded)',
        )

        export_parser.add_argument(
            'file_path',
            type=pathlib.Path,
            help='Specify the file to export to'
        )

        export_parser.add_argument(
            'block_number',
            type=int,
            help='Specify the block number to be exported'
        )

        export_parser.add_argument(
            "--append",
            action="store_true",
            help="Disable peer discovery",
        )

        export_parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Disable peer discovery",
        )

        export_parser.set_defaults(func=cls.run_export)

    @classmethod
    def run_export(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        logger = cls.get_logger()

        chain = get_chain(trinity_config)
        try:
            block = chain.get_canonical_block_by_number(args.block_number)
        except HeaderNotFound:
            logger.error("Block number %s does not exist in the database", args.block_number)
            return

        logger.info("Exporting %s", block)

        block_bytes = rlp.encode(block)

        if args.file_path.exists() and not (args.append or args.overwrite):
            logger.error(
                "%s does exist. Must use `--append` or `--overwrite` to proceed.", args.file_path
            )
            return

        parent_dir = args.file_path.parent

        if not parent_dir.exists():
            parent_dir.mkdir(parents=True)

        write_mode = 'w+b' if not args.append else 'a+b'

        logger.info("Writing %s bytes to %s", len(block_bytes), args.file_path)

        with open(args.file_path, write_mode) as export_file:
            export_file.write(block_bytes)

        logger.info("Successfully exported %s", block)
