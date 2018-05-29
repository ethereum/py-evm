import asyncio
import logging
import signal
import sys
from typing import Type

from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)
from evm.db.backends.base import BaseDB
from evm.db.backends.level import LevelDB

from p2p.service import BaseService

from trinity.chains import (
    initialize_data_dir,
    is_data_dir_initialized,
    serve_chaindb,
)
from trinity.console import (
    console,
)
from trinity.cli_parser import (
    parser,
)
from trinity.config import (
    ChainConfig,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity.utils.logging import (
    setup_trinity_logging,
    with_queued_logging,
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.version import (
    construct_trinity_client_identifier,
)


PRECONFIGURED_NETWORKS = {MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID}


TRINITY_HEADER = (
    "\n"
    "  ______     _       _ __       \n"
    " /_  __/____(_)___  (_) /___  __\n"
    "  / / / ___/ / __ \/ / __/ / / /\n"
    " / / / /  / / / / / / /_/ /_/ / \n"
    "/_/ /_/  /_/_/ /_/_/\__/\__, /  \n"
    "                       /____/   "
)


def main() -> None:
    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper())

    if args.network_id not in PRECONFIGURED_NETWORKS:
        raise NotImplementedError(
            "Unsupported network id: {0}.  Only the ropsten and mainnet "
            "networks are supported.".format(args.network_id)
        )

    chain_config = ChainConfig.from_parser_args(args)

    if not is_data_dir_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        initialize_data_dir(chain_config)

    logger, log_queue, listener = setup_trinity_logging(chain_config, log_level)

    # if console command, run the trinity CLI
    if args.subcommand == 'attach':
        console(chain_config.jsonrpc_ipc_path, use_ipython=not args.vanilla_shell)
        sys.exit(0)

    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    logging_kwargs = {
        'log_queue': log_queue,
        'log_level': log_level,
    }

    # First initialize the database process.
    database_server_process = ctx.Process(
        target=run_database_process,
        args=(
            chain_config,
            LevelDB,
        ),
        kwargs=logging_kwargs,
    )

    networking_process = ctx.Process(
        target=launch_node,
        args=(chain_config, ),
        kwargs=logging_kwargs,
    )

    # start the processes
    database_server_process.start()
    wait_for_ipc(chain_config.database_ipc_path)

    networking_process.start()

    try:
        if args.subcommand == 'console':
            console(chain_config.jsonrpc_ipc_path, use_ipython=not args.vanilla_shell)
        else:
            networking_process.join()
    except KeyboardInterrupt:
        logger.info('Keyboard Interrupt: Stopping')
        kill_process_gracefully(networking_process)
        logger.info('KILLED networking_process')
        kill_process_gracefully(database_server_process)
        logger.info('KILLED database_server_process')


@with_queued_logging
def run_database_process(chain_config: ChainConfig, db_class: Type[BaseDB]) -> None:
    base_db = db_class(db_path=chain_config.database_dir)

    serve_chaindb(chain_config, base_db)


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


@with_queued_logging
def launch_node(chain_config: ChainConfig) -> None:
    display_launch_logs(chain_config)

    NodeClass = chain_config.node_class
    node = NodeClass(chain_config)

    run_service_until_quit(node)


def display_launch_logs(chain_config: ChainConfig) -> None:
    logger = logging.getLogger('trinity')
    logger.info(TRINITY_HEADER)
    logger.info(construct_trinity_client_identifier())


def run_service_until_quit(service: BaseService) -> None:
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(exit_on_signal(service))
    asyncio.ensure_future(service.run())
    loop.run_forever()
    loop.close()
