import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
from multiprocessing.managers import (
    BaseManager,
)
import signal
import sys
from typing import Type

from evm.db.backends.base import BaseDB
from evm.db.backends.level import LevelDB
from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from p2p.peer import (
    LESPeer,
    HardCodedNodesPeerPool,
)
from p2p.server import Server

from trinity.chains import (
    ChainProxy,
    initialize_data_dir,
    is_data_dir_initialized,
    serve_chaindb,
)
from trinity.chains.mainnet import (
    MainnetLightChain,
)
from trinity.chains.ropsten import (
    RopstenLightChain,
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
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.chains import (
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


PRECONFIGURED_NETWORKS = {MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID}


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


@with_queued_logging
def run_lightnode_process(chain_config: ChainConfig) -> None:

    manager = create_dbmanager(chain_config.database_ipc_path)
    headerdb = manager.get_headerdb()  # type: ignore

    if chain_config.network_id == MAINNET_NETWORK_ID:
        chain_class = MainnetLightChain  # type: ignore
    elif chain_config.network_id == ROPSTEN_NETWORK_ID:
        chain_class = RopstenLightChain  # type: ignore
    else:
        raise NotImplementedError(
            "Only the mainnet and ropsten chains are currently supported"
        )
    discovery = None
    peer_pool = HardCodedNodesPeerPool(
        LESPeer, headerdb, chain_config.network_id, chain_config.nodekey, discovery)
    chain = chain_class(headerdb, peer_pool)

    loop = asyncio.get_event_loop()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, chain.cancel_token.trigger)

    rpc = RPCServer(chain)
    ipc_server = IPCServer(rpc, chain_config.jsonrpc_ipc_path)

    async def run_chain(chain):
        try:
            asyncio.ensure_future(chain.peer_pool.run())
            asyncio.ensure_future(ipc_server.run())
            await chain.run()
        finally:
            await ipc_server.stop()
            await chain.peer_pool.cancel()
            await chain.stop()

    loop.run_until_complete(run_chain(chain))
    loop.close()


@with_queued_logging
def run_fullnode_process(chain_config: ChainConfig, port: int) -> None:

    manager = create_dbmanager(chain_config.database_ipc_path)
    db = manager.get_db()  # type: ignore
    headerdb = manager.get_headerdb()  # type: ignore
    chaindb = manager.get_chaindb()  # type: ignore
    chain = manager.get_chain()  # type: ignore

    peer_pool_class = HardCodedNodesPeerPool
    server = Server(
        chain_config.nodekey, port, chain, chaindb, headerdb, db, chain_config.network_id,
        peer_pool_class=peer_pool_class)

    loop = asyncio.get_event_loop()
    # Use a ProcessPoolExecutor as the default so that we can offload cpu-intensive tasks from the
    # main thread.
    loop.set_default_executor(ProcessPoolExecutor())
    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint():
        await sigint_received.wait()
        await server.cancel()
        loop.stop()

    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(server.run())
    loop.run_forever()
    loop.close()
