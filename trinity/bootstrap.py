import asyncio
from argparse import ArgumentParser, Namespace
import argcomplete
import logging
import multiprocessing
import os
import signal
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Tuple,
    Type,
)

from lahja import (
    ConnectionConfig,
)

from trinity.exceptions import (
    AmbigiousFileSystem,
    MissingPath,
)
from trinity.initialization import (
    initialize_data_dir,
    is_data_dir_initialized,
)
from trinity.cli_parser import (
    parser,
    subparser,
)
from trinity.config import (
    BaseAppConfig,
    TrinityConfig,
)
from trinity.constants import (
    MAINNET_NETWORK_ID,
    MAIN_EVENTBUS_ENDPOINT,
    ROPSTEN_NETWORK_ID,
)
from trinity.endpoint import (
    TrinityMainEventBusEndpoint,
)
from trinity.extensibility import (
    BasePlugin,
    PluginManager,
)
from trinity.events import (
    ShutdownRequest,
)
from trinity._utils.ipc import (
    kill_process_gracefully,
    remove_dangling_ipc_files,
)
from trinity._utils.logging import (
    enable_warnings_by_default,
    setup_log_levels,
    setup_trinity_stderr_logging,
    setup_trinity_file_and_queue_logging,
)
from trinity._utils.version import (
    construct_trinity_client_identifier,
    is_prerelease,
)


PRECONFIGURED_NETWORKS = {MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID}


TRINITY_HEADER = "\n".join((
    "\n"
    r"      ______     _       _ __       ",
    r"     /_  __/____(_)___  (_) /___  __",
    r"      / / / ___/ / __ \/ / __/ / / /",
    r"     / / / /  / / / / / / /_/ /_/ / ",
    r"    /_/ /_/  /_/_/ /_/_/\__/\__, /  ",
    r"                           /____/   ",
))

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


BootFn = Callable[[
    Namespace,
    TrinityConfig,
    Dict[str, Any],
    PluginManager,
    logging.handlers.QueueListener,
    TrinityMainEventBusEndpoint,
    logging.Logger
], Tuple[multiprocessing.Process, ...]]


def main_entry(trinity_boot: BootFn,
               app_identifier: str,
               plugins: Iterable[Type[BasePlugin]],
               sub_configs: Iterable[Type[BaseAppConfig]]) -> None:

    main_endpoint = TrinityMainEventBusEndpoint(name=MAIN_EVENTBUS_ENDPOINT)

    plugin_manager = PluginManager(
        main_endpoint,
        plugins
    )
    plugin_manager.amend_argparser_config(parser, subparser)

    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if not args.genesis and args.network_id not in PRECONFIGURED_NETWORKS:
        raise NotImplementedError(
            f"Unsupported network id: {args.network_id}. To use a network besides "
            "mainnet or ropsten, you must supply a genesis file with a flag, like "
            "`--genesis path/to/genesis.json`, also you must specify a data "
            "directory with `--data-dir path/to/data/directory`"
        )

    # The `common_log_level` is derived from `--log-level <Level>` / `-l <Level>` without
    # specifying any module. If present, it is used for both `stderr` and `file` logging.
    common_log_level = args.log_levels and args.log_levels.get(None)
    has_ambigous_logging_config = ((
        common_log_level is not None and
        args.stderr_log_level is not None
    ) or (
        common_log_level is not None and
        args.file_log_level is not None
    ))

    if has_ambigous_logging_config:
        parser.error(
            f"""\n
            Ambiguous logging configuration: The `--log-level (-l)` flag sets the
            log level for both file and stderr logging.
            To configure different log level for file and stderr logging,
            remove the `--log-level` flag and use `--stderr-log-level` and/or
            `--file-log-level` separately.
            Alternatively, remove the `--stderr-log-level` and/or `--file-log-level`
            flags to share one single log level across both handlers.
            """
        )

    if is_prerelease():
        # this modifies the asyncio logger, but will be overridden by any custom settings below
        enable_warnings_by_default()

    stderr_logger, handler_stream = setup_trinity_stderr_logging(
        args.stderr_log_level or common_log_level
    )

    if args.log_levels:
        setup_log_levels(args.log_levels)

    try:
        trinity_config = TrinityConfig.from_parser_args(args, app_identifier, sub_configs)
    except AmbigiousFileSystem:
        parser.error(TRINITY_AMBIGIOUS_FILESYSTEM_INFO)

    if not is_data_dir_initialized(trinity_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        try:
            initialize_data_dir(trinity_config)
        except AmbigiousFileSystem:
            parser.error(TRINITY_AMBIGIOUS_FILESYSTEM_INFO)
        except MissingPath as e:
            parser.error(
                "\n"
                f"It appears that {e.path} does not exist. "
                "Trinity does not attempt to create directories outside of its root path. "
                "Either manually create the path or ensure you are using a data directory "
                "inside the XDG_TRINITY_ROOT path"
            )

    file_logger, log_queue, listener = setup_trinity_file_and_queue_logging(
        stderr_logger,
        handler_stream,
        trinity_config.logfile_path,
        args.file_log_level or common_log_level,
    )

    display_launch_logs(trinity_config)

    # compute the minimum configured log level across all configured loggers.
    min_configured_log_level = min(
        stderr_logger.level,
        file_logger.level,
        *(args.log_levels or {}).values()
    )

    extra_kwargs = {
        'log_queue': log_queue,
        'log_level': min_configured_log_level,
        'log_levels': args.log_levels if args.log_levels else {},
        'profile': args.profile,
    }

    # Plugins can provide a subcommand with a `func` which does then control
    # the entire process from here.
    if hasattr(args, 'func'):
        args.func(args, trinity_config)
        return

    processes = trinity_boot(
        args,
        trinity_config,
        extra_kwargs,
        plugin_manager,
        listener,
        main_endpoint,
        stderr_logger,
    )

    def kill_trinity_with_reason(reason: str) -> None:
        kill_trinity_gracefully(
            trinity_config,
            stderr_logger,
            processes,
            plugin_manager,
            main_endpoint,
            reason=reason
        )

    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(trinity_boot_coro(
            kill_trinity_with_reason,
            main_endpoint,
            trinity_config,
            plugin_manager,
            args, extra_kwargs,
        ))
        loop.add_signal_handler(signal.SIGTERM, lambda: kill_trinity_with_reason("SIGTERM"))
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        kill_trinity_with_reason("CTRL+C / Keyboard Interrupt")


async def trinity_boot_coro(kill_trinity, main_endpoint, trinity_config,  # type: ignore
                            plugin_manager, args, extra_kwargs) -> None:
    # We postpone EventBus connection until here because we don't want one in cases where
    # a plugin just redefines the `trinity` command such as `trinity fix-unclean-shutdown`
    main_connection_config = ConnectionConfig.from_name(
        MAIN_EVENTBUS_ENDPOINT,
        trinity_config.ipc_dir
    )
    await main_endpoint.start()
    await main_endpoint.start_server(main_connection_config.path)

    main_endpoint.track_and_propagate_available_endpoints()

    main_endpoint.subscribe(
        ShutdownRequest,
        lambda ev: kill_trinity(ev.reason)
    )

    plugin_manager.prepare(args, trinity_config, extra_kwargs)


def display_launch_logs(trinity_config: TrinityConfig) -> None:
    logger = logging.getLogger('trinity')
    logger.info(TRINITY_HEADER)
    logger.info("Started main process (pid=%d)", os.getpid())
    logger.info(construct_trinity_client_identifier())
    logger.info("Trinity DEBUG log file is created at %s", str(trinity_config.logfile_path))


def kill_trinity_gracefully(trinity_config: TrinityConfig,
                            logger: logging.Logger,
                            processes: Iterable[multiprocessing.Process],
                            plugin_manager: PluginManager,
                            main_endpoint: TrinityMainEventBusEndpoint,
                            reason: str=None) -> None:
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

    hint = f"({reason})" if reason else f""
    logger.info('Shutting down Trinity %s', hint)
    plugin_manager.shutdown_blocking()
    for process in processes:
        # Our sub-processes will have received a SIGINT already (see comment above), so here we
        # wait 2s for them to finish cleanly, and if they fail we kill them for real.
        process.join(2)
        if process.is_alive():
            kill_process_gracefully(process, logger)
        logger.info('%s process (pid=%d) terminated', process.name, process.pid)

    main_endpoint.stop()
    remove_dangling_ipc_files(logger, trinity_config.ipc_dir, except_file=main_endpoint.ipc_path)

    ArgumentParser().exit(message=f"Trinity shutdown complete {hint}\n")
