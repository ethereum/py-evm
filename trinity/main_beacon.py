from argparse import (
    ArgumentParser,
    Namespace,
)
import logging
import multiprocessing
from typing import (
    Any,
    Dict,
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
from trinity.config import (
    TrinityConfig,
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
from trinity._utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity._utils.logging import (
    with_queued_logging,
)
from trinity._utils.mp import (
    ctx,
)
from trinity._utils.profiling import (
    setup_cprofiler,
)


def main_beacon() -> None:
    main_entry(
        trinity_boot,
        APP_IDENTIFIER_BEACON,
        get_components_for_beacon_client(),
        (BeaconAppConfig,)
    )


def trinity_boot(args: Namespace,
                 trinity_config: TrinityConfig,
                 extra_kwargs: Dict[str, Any],
                 listener: logging.handlers.QueueListener,
                 logger: logging.Logger) -> Tuple[multiprocessing.Process, ...]:
    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    ensure_beacon_dirs(trinity_config.get_app_config(BeaconAppConfig))

    # First initialize the database process.
    database_server_process = ctx.Process(
        name="DB",
        target=run_database_process,
        args=(
            trinity_config,
            LevelDB,
        ),
        kwargs=extra_kwargs,
    )

    # start the processes
    database_server_process.start()
    logger.info("Started DB server process (pid=%d)", database_server_process.pid)

    try:
        wait_for_ipc(trinity_config.database_ipc_path)
    except TimeoutError as e:
        logger.error("Timeout waiting for database to start.  Exiting...")
        kill_process_gracefully(database_server_process, logger)
        ArgumentParser().error(message="Timed out waiting for database start")
        return None

    return (database_server_process,)


@setup_cprofiler('profile_db_process')
@with_queued_logging
def run_database_process(trinity_config: TrinityConfig, db_class: Type[LevelDB]) -> None:
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
