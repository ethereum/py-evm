import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
from multiprocessing.managers import (
    BaseManager,
)
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

from p2p.discovery import DiscoveryProtocol
from p2p.kademlia import Address
from p2p.peer import (
    LESPeer,
    PreferredNodePeerPool,
)
from p2p.server import Server
from p2p.service import BaseService

from trinity.chains import (
    ChainProxy,
    initialize_data_dir,
    is_data_dir_initialized,
    serve_chaindb,
)
from trinity.chains.header import (
    AsyncHeaderChainProxy,
)
from trinity.console import (
    console,
)
from trinity.constants import (
    SYNC_LIGHT,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.db.header import AsyncHeaderDBProxy
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
    logger, log_queue, listener = setup_trinity_logging(log_level)

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

    # TODO: Combine run_fullnode_process/run_lightnode_process into a single function that simply
    # passes the sync mode to p2p.Server, which then selects the appropriate sync service.
    if args.sync_mode == SYNC_LIGHT:
        networking_process = ctx.Process(
            target=run_lightnode_process,
            args=(chain_config, ),
            kwargs=logging_kwargs,
        )
    else:
        networking_process = ctx.Process(
            target=run_fullnode_process,
            args=(chain_config, args.port),
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


def create_dbmanager(ipc_path: str) -> BaseManager:
    """
    We're still using 'str' here on param ipc_path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly
    """
    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', proxytype=DBProxy)  # type: ignore
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)  # type: ignore
    DBManager.register('get_chain', proxytype=ChainProxy)  # type: ignore
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)  # type: ignore
    DBManager.register('get_header_chain', proxytype=AsyncHeaderChainProxy)  # type: ignore

    manager = DBManager(address=ipc_path)  # type: ignore
    manager.connect()  # type: ignore
    return manager


async def exit_on_signal(service_to_exit: BaseService) -> None:
    loop = asyncio.get_event_loop()
    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        # TODO replace with OS-independent solution:
        loop.add_signal_handler(sig, sigint_received.set)

    await sigint_received.wait()
    try:
        await service_to_exit.cancel()
    finally:
        loop.stop()


@with_queued_logging
def run_lightnode_process(chain_config: ChainConfig) -> None:
    logger = logging.getLogger('trinity')
    logger.info(TRINITY_HEADER)
    logger.info(construct_trinity_client_identifier())
    logger.info(
        "enode://%s@%s:%s",
        chain_config.nodekey.to_hex()[2:],
        "[:]",
        chain_config.port,
    )
    logger.info('network: %s', chain_config.network_id)

    manager = create_dbmanager(chain_config.database_ipc_path)
    headerdb = manager.get_headerdb()  # type: ignore

    NodeClass = chain_config.node_class
    discovery = DiscoveryProtocol(
        chain_config.nodekey,
        Address('0.0.0.0', chain_config.port, chain_config.port),
        bootstrap_nodes=chain_config.bootstrap_nodes,
    )
    peer_pool = PreferredNodePeerPool(
        LESPeer,
        headerdb,
        chain_config.network_id,
        chain_config.nodekey,
        discovery,
        preferred_nodes=chain_config.preferred_nodes,
    )
    node = NodeClass(headerdb, peer_pool, chain_config.jsonrpc_ipc_path)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.create_datagram_endpoint(
        lambda: discovery,
        local_addr=('0.0.0.0', chain_config.port)
    ))
    asyncio.ensure_future(discovery.bootstrap())
    asyncio.ensure_future(exit_on_signal(node))
    asyncio.ensure_future(node.run())
    loop.run_forever()

    loop.close()


@with_queued_logging
def run_fullnode_process(chain_config: ChainConfig, port: int) -> None:
    logger = logging.getLogger('trinity')
    logger.info(TRINITY_HEADER)
    logger.info(construct_trinity_client_identifier())

    manager = create_dbmanager(chain_config.database_ipc_path)
    db = manager.get_db()  # type: ignore
    headerdb = manager.get_headerdb()  # type: ignore
    chaindb = manager.get_chaindb()  # type: ignore
    chain = manager.get_chain()  # type: ignore

    peer_pool_class = PreferredNodePeerPool
    server = Server(
        chain_config.nodekey,
        port,
        chain,
        chaindb,
        headerdb,
        db,
        chain_config.network_id,
        peer_pool_class=peer_pool_class,
        bootstrap_nodes=chain_config.bootstrap_nodes,
    )

    loop = asyncio.get_event_loop()
    # Use a ProcessPoolExecutor as the default so that we can offload cpu-intensive tasks from the
    # main thread.
    loop.set_default_executor(ProcessPoolExecutor())
    asyncio.ensure_future(exit_on_signal(server))
    asyncio.ensure_future(server.run())
    loop.run_forever()
    loop.close()
