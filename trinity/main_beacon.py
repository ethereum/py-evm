from argparse import ArgumentParser, Namespace
import asyncio
import logging
import signal
from typing import (
    Any,
    Dict,
)

from lahja import (
    EventBus,
    Endpoint,
)

from eth.db.backends.level import LevelDB

from trinity.bootstrap import (
    kill_trinity_gracefully,
    main_entry,
    run_database_process,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.events import (
    ShutdownRequest
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.plugins.registry import (
    BASE_PLUGINS,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity.utils.mp import (
    ctx,
)


def main_beacon() -> None:
    main_entry(trinity_boot, BASE_PLUGINS)


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

    # networking process needs the IPC socket file provided by the database process
    try:
        wait_for_ipc(trinity_config.database_ipc_path)
    except TimeoutError as e:
        logger.error("Timeout waiting for database to start.  Exiting...")
        kill_process_gracefully(database_server_process, logger)
        ArgumentParser().error(message="Timed out waiting for database start")

    def kill_trinity_with_reason(reason: str) -> None:
        kill_trinity_gracefully(
            logger,
            (database_server_process,),
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

    kill_trinity_with_reason("No beacon support yet. SOON!")

    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: kill_trinity_with_reason("SIGTERM"))
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        kill_trinity_with_reason("CTRL+C / Keyboard Interrupt")
