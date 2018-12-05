from argparse import ArgumentParser, Namespace
import asyncio
import logging
import signal
from typing import (
    Any,
    Dict,
    Iterable,
)

from lahja import (
    EventBus,
    Endpoint,
)

from eth.db.backends.level import LevelDB

from p2p.service import BaseService

from trinity.bootstrap import (
    kill_trinity_gracefully,
    main_entry,
    run_database_process,
    setup_plugins,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.constants import (
    NETWORKING_EVENTBUS_ENDPOINT,
)
from trinity.events import (
    ShutdownRequest
)
from trinity.extensibility import (
    BasePlugin,
    PluginManager,
    SharedProcessScope,
)
from trinity.plugins.registry import (
    BASE_PLUGINS,
    discover_plugins,
    ETH1_NODE_PLUGINS,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity.utils.logging import (
    with_queued_logging,
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.profiling import (
    setup_cprofiler,
)
from trinity.utils.shutdown import (
    exit_signal_with_service,
)


def get_all_plugins() -> Iterable[BasePlugin]:
    return BASE_PLUGINS + ETH1_NODE_PLUGINS + discover_plugins()


def main() -> None:
    main_entry(trinity_boot, get_all_plugins())


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

    networking_endpoint = event_bus.create_endpoint(NETWORKING_EVENTBUS_ENDPOINT)
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

    networking_process = ctx.Process(
        name="networking",
        target=launch_node,
        args=(args, trinity_config, networking_endpoint,),
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

    networking_process.start()
    logger.info("Started networking process (pid=%d)", networking_process.pid)

    def kill_trinity_with_reason(reason: str) -> None:
        kill_trinity_gracefully(
            logger,
            (database_server_process, networking_process),
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


@setup_cprofiler('launch_node')
@with_queued_logging
def launch_node(args: Namespace, trinity_config: TrinityConfig, endpoint: Endpoint) -> None:
    with trinity_config.process_id_file('networking'):

        NodeClass = trinity_config.node_class
        node = NodeClass(endpoint, trinity_config)
        loop = node.get_event_loop()

        endpoint.connect_no_wait(loop)
        # This is a second PluginManager instance governing plugins in a shared process.
        plugin_manager = setup_plugins(SharedProcessScope(endpoint), get_all_plugins())
        plugin_manager.prepare(args, trinity_config)

        asyncio.ensure_future(handle_networking_exit(node, plugin_manager, endpoint), loop=loop)
        asyncio.ensure_future(node.run(), loop=loop)
        loop.run_forever()
        loop.close()


async def handle_networking_exit(service: BaseService,
                                 plugin_manager: PluginManager,
                                 endpoint: Endpoint) -> None:

    async with exit_signal_with_service(service):
        await plugin_manager.shutdown()
        endpoint.stop()
