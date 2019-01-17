from argparse import (
    ArgumentParser,
    Namespace,
)
import asyncio
import logging
import signal
from typing import (
    Any,
    Dict,
    Type,
)

from lahja import (
    EventBus,
    Endpoint,
)

from eth.db.backends.base import (
    BaseDB,
)
from eth.db.backends.level import (
    LevelDB,
)

from trinity.bootstrap import (
    kill_trinity_gracefully,
    main_entry,
)
from trinity.config import (
    TrinityConfig,
    BeaconAppConfig
)
from trinity.constants import (
    APP_IDENTIFIER_BEACON,
)
from trinity.db.beacon.manager import (
    create_db_server_manager,
)
from trinity.events import (
    ShutdownRequest
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.initialization import (
    ensure_beacon_dirs,
)
from trinity.plugins.registry import (
    BASE_PLUGINS,
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


def main_beacon() -> None:
    main_entry(trinity_boot, APP_IDENTIFIER_BEACON, BASE_PLUGINS, (BeaconAppConfig,))


def trinity_boot(args: Namespace,
                 trinity_config: TrinityConfig,
                 extra_kwargs: Dict[str, Any],
                 plugin_manager: PluginManager,
                 listener: logging.handlers.QueueListener,
                 event_bus: EventBus,
                 main_endpoint: Endpoint,
                 logger: logging.Logger) -> None:
    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    ensure_beacon_dirs(trinity_config.get_app_config(BeaconAppConfig))

    event_bus.start()

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

    def kill_trinity_with_reason(reason: str) -> None:
        kill_trinity_gracefully(
            logger,
            (),
            plugin_manager,
            main_endpoint,
            event_bus,
            reason=reason
        )

    main_endpoint.subscribe(
        ShutdownRequest,
        lambda ev: kill_trinity_with_reason(ev.reason)
    )

    plugin_manager.prepare(args, trinity_config, extra_kwargs)

    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: kill_trinity_with_reason("SIGTERM"))
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        kill_trinity_with_reason("CTRL+C / Keyboard Interrupt")


@setup_cprofiler('run_database_process')
@with_queued_logging
def run_database_process(trinity_config: TrinityConfig, db_class: Type[BaseDB]) -> None:
    with trinity_config.process_id_file('database'):
        app_config = trinity_config.get_app_config(BeaconAppConfig)

        base_db = db_class(db_path=app_config.database_dir)

        manager = create_db_server_manager(trinity_config, base_db)
        serve_until_sigint(manager)
