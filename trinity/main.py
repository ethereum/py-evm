from argparse import Namespace
import asyncio
import logging
import signal
import sys
import time
from typing import (
    Any,
    Dict,
    Type,
)

from eth.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from eth.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)
from eth.db.backends.base import BaseDB
from eth.db.backends.level import LevelDB

from p2p.service import BaseService

from trinity.exceptions import (
    AmbigiousFileSystem,
    MissingPath,
)
from trinity.chains import (
    initialize_data_dir,
    is_data_dir_initialized,
    serve_chaindb,
)
from trinity.cli_parser import (
    parser,
    subparser,
)
from trinity.config import (
    ChainConfig,
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.extensibility.events import (
    TrinityStartupEvent
)
from trinity.plugins.registry import (
    ENABLED_PLUGINS
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
    kill_process_id_gracefully,
)
from trinity.utils.logging import (
    setup_trinity_stderr_logging,
    setup_trinity_file_and_queue_logging,
    with_queued_logging,
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.profiling import (
    setup_cprofiler,
)
from trinity.utils.version import (
    construct_trinity_client_identifier,
)


PRECONFIGURED_NETWORKS = {MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID}


TRINITY_HEADER = (
    "\n"
    "      ______     _       _ __       \n"
    "     /_  __/____(_)___  (_) /___  __\n"
    "      / / / ___/ / __ \/ / __/ / / /\n"
    "     / / / /  / / / / / / /_/ /_/ / \n"
    "    /_/ /_/  /_/_/ /_/_/\__/\__, /  \n"
    "                           /____/   "
)

TRINITY_AMBIGIOUS_FILESYSTEM_INFO = (
    "Could not initialize data directory\n\n"
    "   One of these conditions must be met:\n"
    "   * HOME environment variable set\n"
    "   * XDG_TRINITY_ROOT environment variable set\n"
    "   * TRINITY_DATA_DIR environment variable set\n"
    "   * --data-dir command line argument is passed\n"
    "\n"
    "   In case the data directory is outside of the trinity root directory\n"
    "   Make sure all paths are pre-initialized as Trinity won't attempt\n"
    "   to create directories outside of the trinity root directory\n"
)


def main() -> None:
    plugin_manager = setup_plugins()
    plugin_manager.amend_argparser_config(parser, subparser)
    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper())

    if args.network_id not in PRECONFIGURED_NETWORKS:
        raise NotImplementedError(
            "Unsupported network id: {0}.  Only the ropsten and mainnet "
            "networks are supported.".format(args.network_id)
        )

    logger, formatter, handler_stream = setup_trinity_stderr_logging(log_level)

    try:
        chain_config = ChainConfig.from_parser_args(args)
    except AmbigiousFileSystem:
        exit_because_ambigious_filesystem(logger)

    if not is_data_dir_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        try:
            initialize_data_dir(chain_config)
        except AmbigiousFileSystem:
            exit_because_ambigious_filesystem(logger)
        except MissingPath as e:
            msg = (
                "\n"
                "It appears that {} does not exist.\n"
                "Trinity does not attempt to create directories outside of its root path\n"
                "Either manually create the path or ensure you are using a data directory\n"
                "inside the XDG_TRINITY_ROOT path"
            ).format(e.path)
            logger.error(msg)
            sys.exit(1)

    logger, log_queue, listener = setup_trinity_file_and_queue_logging(
        logger,
        formatter,
        handler_stream,
        chain_config,
        log_level
    )

    # if cleanup command, try to shutdown dangling processes and exit
    if args.subcommand == 'fix-unclean-shutdown':
        fix_unclean_shutdown(chain_config, logger)
        sys.exit(0)

    display_launch_logs(chain_config)

    extra_kwargs = {
        'log_queue': log_queue,
        'log_level': log_level,
        'profile': args.profile,
    }

    # Plugins can provide a subcommand with a `func` which does then control
    # the entire process from here.
    if hasattr(args, 'func'):
        args.func(args, chain_config)
    else:
        trinity_boot(args, chain_config, extra_kwargs, listener, logger)


def trinity_boot(args: Namespace,
                 chain_config: ChainConfig,
                 extra_kwargs: Dict[str, Any],
                 listener: logging.handlers.QueueListener,
                 logger: logging.Logger) -> None:
    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    # First initialize the database process.
    database_server_process = ctx.Process(
        target=run_database_process,
        args=(
            chain_config,
            LevelDB,
        ),
        kwargs=extra_kwargs,
    )

    networking_process = ctx.Process(
        target=launch_node,
        args=(args, chain_config, ),
        kwargs=extra_kwargs,
    )

    # start the processes
    database_server_process.start()
    logger.info("Started DB server process (pid=%d)", database_server_process.pid)
    wait_for_ipc(chain_config.database_ipc_path)

    networking_process.start()
    logger.info("Started networking process (pid=%d)", networking_process.pid)

    try:
        networking_process.join()
    except KeyboardInterrupt:
        # When a user hits Ctrl+C in the terminal, the SIGINT is sent to all processes in the
        # foreground *process group*, so both our networking and database processes will terminate
        # at the same time and not sequentially as we'd like. That shouldn't be a problem but if
        # we keep getting unhandled BrokenPipeErrors/ConnectionResetErrors like reported in
        # https://github.com/ethereum/py-evm/issues/827, we might want to change the networking
        # process' signal handler to wait until the DB process has terminated before doing its
        # thing.
        # Notice that we still need the kill_process_gracefully() calls here, for when the user
        # simply uses 'kill' to send a signal to the main process, but also because they will
        # perform a non-gracefull shutdown if the process takes too long to terminate.
        logger.info('Keyboard Interrupt: Stopping')
        kill_process_gracefully(database_server_process, logger)
        logger.info('DB server process (pid=%d) terminated', database_server_process.pid)
        # XXX: This short sleep here seems to avoid us hitting a deadlock when attempting to
        # join() the networking subprocess: https://github.com/ethereum/py-evm/issues/940
        time.sleep(0.2)
        kill_process_gracefully(networking_process, logger)
        logger.info('Networking process (pid=%d) terminated', networking_process.pid)


def fix_unclean_shutdown(chain_config: ChainConfig, logger: logging.Logger) -> None:
    logger.info("Cleaning up unclean shutdown...")

    logger.info("Searching for process id files in %s..." % chain_config.data_dir)
    pidfiles = tuple(chain_config.data_dir.glob('*.pid'))
    if len(pidfiles) > 1:
        logger.info('Found %d processes from a previous run. Closing...' % len(pidfiles))
    elif len(pidfiles) == 1:
        logger.info('Found 1 process from a previous run. Closing...')
    else:
        logger.info('Found 0 processes from a previous run. No processes to kill.')

    for pidfile in pidfiles:
        process_id = int(pidfile.read_text())
        kill_process_id_gracefully(process_id, time.sleep, logger)
        try:
            pidfile.unlink()
            logger.info('Manually removed %s after killing process id %d' % (pidfile, process_id))
        except FileNotFoundError:
            logger.debug('pidfile %s was gone after killing process id %d' % (pidfile, process_id))

    db_ipc = chain_config.database_ipc_path
    try:
        db_ipc.unlink()
        logger.info('Removed a dangling IPC socket file for database connections at %s', db_ipc)
    except FileNotFoundError:
        logger.debug('The IPC socket file for database connections at %s was already gone', db_ipc)

    jsonrpc_ipc = chain_config.jsonrpc_ipc_path
    try:
        jsonrpc_ipc.unlink()
        logger.info(
            'Removed a dangling IPC socket file for JSON-RPC connections at %s',
            jsonrpc_ipc,
        )
    except FileNotFoundError:
        logger.debug(
            'The IPC socket file for JSON-RPC connections at %s was already gone',
            jsonrpc_ipc,
        )


@setup_cprofiler('run_database_process')
@with_queued_logging
def run_database_process(chain_config: ChainConfig, db_class: Type[BaseDB]) -> None:
    with chain_config.process_id_file('database'):
        base_db = db_class(db_path=chain_config.database_dir)

        serve_chaindb(chain_config, base_db)


def exit_because_ambigious_filesystem(logger: logging.Logger) -> None:
    logger.error(TRINITY_AMBIGIOUS_FILESYSTEM_INFO)
    sys.exit(1)


async def exit_on_signal(service_to_exit: BaseService) -> None:
    loop = asyncio.get_event_loop()
    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        # TODO also support Windows
        loop.add_signal_handler(sig, sigint_received.set)

    await sigint_received.wait()
    try:
        await service_to_exit.cancel()
    finally:
        loop.stop()


@setup_cprofiler('launch_node')
@with_queued_logging
def launch_node(args: Namespace, chain_config: ChainConfig) -> None:
    with chain_config.process_id_file('networking'):
        NodeClass = chain_config.node_class
        # Temporary hack: We setup a second instance of the PluginManager.
        # The first instance was only to configure the ArgumentParser whereas
        # for now, the second instance that lives inside the networking process
        # performs the bulk of the work. In the future, the PluginManager
        # should probably live in its own process and manage whether plugins
        # run in the shared plugin process or spawn their own.
        plugin_manager = setup_plugins()
        plugin_manager.broadcast(TrinityStartupEvent(
            args,
            chain_config
        ))

        node = NodeClass(plugin_manager, chain_config)

        run_service_until_quit(node)


def display_launch_logs(chain_config: ChainConfig) -> None:
    logger = logging.getLogger('trinity')
    logger.info(TRINITY_HEADER)
    logger.info(construct_trinity_client_identifier())
    logger.info("Trinity DEBUG log file is created at %s", str(chain_config.logfile_path))


def run_service_until_quit(service: BaseService) -> None:
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(exit_on_signal(service))
    asyncio.ensure_future(service.run())
    loop.run_forever()
    loop.close()


def setup_plugins() -> PluginManager:
    plugin_manager = PluginManager()
    # TODO: Implement auto-discovery of plugins based on some convention/configuration scheme
    plugin_manager.register(ENABLED_PLUGINS)

    return plugin_manager
