from argparse import ArgumentParser, Namespace
import logging
import multiprocessing
from typing import (
    Any,
    Dict,
    Tuple,
    Type,
)

from eth.db.backends.base import BaseDB
from eth.db.backends.level import LevelDB

from trinity.bootstrap import (
    main_entry,
)
from trinity.config import (
    TrinityConfig,
    Eth1AppConfig,
)
from trinity.constants import (
    APP_IDENTIFIER_ETH1,
)
from trinity.db.eth1.manager import (
    create_db_server_manager,
)
from trinity.endpoint import (
    TrinityMainEventBusEndpoint,
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.initialization import (
    ensure_eth1_dirs,
)
from trinity.plugins.registry import (
    get_plugins_for_eth1_client,
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
from trinity._utils.proxy import (
    serve_until_sigint,
)


def main() -> None:
    main_entry(trinity_boot, APP_IDENTIFIER_ETH1, get_plugins_for_eth1_client(), (Eth1AppConfig,))


def trinity_boot(args: Namespace,
                 trinity_config: TrinityConfig,
                 extra_kwargs: Dict[str, Any],
                 plugin_manager: PluginManager,
                 listener: logging.handlers.QueueListener,
                 main_endpoint: TrinityMainEventBusEndpoint,
                 logger: logging.Logger) -> Tuple[multiprocessing.Process, ...]:
    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    ensure_eth1_dirs(trinity_config.get_app_config(Eth1AppConfig))

    # First initialize the database process.
    database_server_process: multiprocessing.Process = ctx.Process(
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

    # networking process needs the IPC socket file provided by the database process
    try:
        wait_for_ipc(trinity_config.database_ipc_path)
    except TimeoutError as e:
        logger.error("Timeout waiting for database to start.  Exiting...")
        kill_process_gracefully(database_server_process, logger)
        ArgumentParser().error(message="Timed out waiting for database start")
        return None

    return (database_server_process,)


@setup_cprofiler('run_database_process')
@with_queued_logging
def run_database_process(trinity_config: TrinityConfig, db_class: Type[BaseDB]) -> None:
    with trinity_config.process_id_file('database'):
        app_config = trinity_config.get_app_config(Eth1AppConfig)

        base_db = db_class(db_path=app_config.database_dir)

        manager = create_db_server_manager(trinity_config, base_db)
        serve_until_sigint(manager)
