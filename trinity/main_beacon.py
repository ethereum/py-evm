from argparse import (
    ArgumentParser,
)
import logging
import multiprocessing
from typing import (
    Tuple,
    Type,
)

from eth.db.backends.level import (
    LevelDB,
)

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.types.blocks import BeaconBlock

from trinity.bootstrap import (
    main_entry,
)
from trinity.boot_info import BootInfo
from trinity.config import (
    BeaconAppConfig
)
from trinity.constants import (
    APP_IDENTIFIER_BEACON,
)
from trinity.db.manager import DBManager
from trinity.initialization import (
    ensure_beacon_dirs,
    initialize_beacon_database,
    is_beacon_database_initialized,
)
from trinity.components.registry import (
    get_components_for_beacon_client,
)
from trinity._utils.logging import setup_child_process_logging
from trinity._utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity._utils.mp import (
    ctx,
)


def main_beacon() -> None:
    main_entry(
        trinity_boot,
        APP_IDENTIFIER_BEACON,
        get_components_for_beacon_client(),
        (BeaconAppConfig,)
    )


def trinity_boot(boot_info: BootInfo) -> Tuple[multiprocessing.Process, ...]:
    logger = logging.getLogger('trinity')

    trinity_config = boot_info.trinity_config

    ensure_beacon_dirs(trinity_config.get_app_config(BeaconAppConfig))

    # First initialize the database process.
    database_server_process = ctx.Process(
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
        app_config = trinity_config.get_app_config(BeaconAppConfig)
        chain_config = app_config.get_chain_config()

        base_db = db_class(db_path=app_config.database_dir)
        chaindb = BeaconChainDB(base_db, chain_config.genesis_config)

        if not is_beacon_database_initialized(chaindb, BeaconBlock):
            initialize_beacon_database(chain_config, chaindb, base_db, BeaconBlock)

        manager = DBManager(base_db)
        with manager.run(trinity_config.database_ipc_path):
            try:
                manager.wait_stopped()
            except KeyboardInterrupt:
                pass
