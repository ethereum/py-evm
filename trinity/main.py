from argparse import ArgumentParser
import logging
import multiprocessing
from typing import (
    Tuple,
    Type,
)

from eth.db.backends.level import LevelDB
from eth.db.chain import ChainDB

from trinity.boot_info import BootInfo
from trinity.bootstrap import (
    main_entry,
)
from trinity.config import (
    Eth1AppConfig,
)
from trinity.constants import (
    APP_IDENTIFIER_ETH1,
)
from trinity.db.manager import DBManager
from trinity.initialization import (
    is_database_initialized,
    initialize_database,
    ensure_eth1_dirs,
)
from trinity.components.registry import (
    get_components_for_eth1_client,
)
from trinity._utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity._utils.logging import (
    setup_child_process_logging,
)
from trinity._utils.mp import (
    ctx,
)


def main() -> None:
    main_entry(
        trinity_boot,
        APP_IDENTIFIER_ETH1,
        get_components_for_eth1_client(),
        (Eth1AppConfig,)
    )


def trinity_boot(boot_info: BootInfo) -> Tuple[multiprocessing.Process]:
    trinity_config = boot_info.trinity_config
    ensure_eth1_dirs(trinity_config.get_app_config(Eth1AppConfig))

    logger = logging.getLogger('trinity')

    # First initialize the database process.
    database_server_process: multiprocessing.Process = ctx.Process(
        name="DB",
        target=run_database_process,
        args=(
            boot_info,
            LevelDB,
        ),
    )

    # start the processes
    database_server_process.start()
    logger.info("Started DB server process (pid=%d)", database_server_process.pid)

    # networking process needs the IPC socket file provided by the database process
    try:
        wait_for_ipc(trinity_config.database_ipc_path)
    except TimeoutError:
        logger.error("Timeout waiting for database to start.  Exiting...")
        kill_process_gracefully(database_server_process, logger)
        ArgumentParser().error(message="Timed out waiting for database start")
        return None

    return (database_server_process,)


def run_database_process(boot_info: BootInfo, db_class: Type[LevelDB]) -> None:
    setup_child_process_logging(boot_info)
    trinity_config = boot_info.trinity_config

    with trinity_config.process_id_file('database'):
        app_config = trinity_config.get_app_config(Eth1AppConfig)

        base_db = db_class(db_path=app_config.database_dir)
        chaindb = ChainDB(base_db)

        if not is_database_initialized(chaindb):
            chain_config = app_config.get_chain_config()
            initialize_database(chain_config, chaindb, base_db)

        manager = DBManager(base_db)
        with manager.run(trinity_config.database_ipc_path):
            try:
                manager.wait_stopped()
            except KeyboardInterrupt:
                pass
