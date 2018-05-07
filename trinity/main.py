import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
from multiprocessing.managers import (
    BaseManager,
)
import signal
import sys
from typing import Type

from evm.db.backends.level import LevelDB
from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from p2p.exceptions import OperationCancelled
from p2p.sync import FullNodeSyncer
from p2p.peer import (
    ETHPeer,
    LESPeer,
    HardCodedNodesPeerPool,
)

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
from trinity.console import (
    console,
)
from trinity.constants import (
    SYNC_LIGHT,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
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

    # TODO: needs to be made generic once we have non-light modes.
    pool_class = HardCodedNodesPeerPool

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
    networking_proc_fn = run_fullnode_process
    if args.sync_mode == SYNC_LIGHT:
        networking_proc_fn = run_lightnode_process
    networking_process = ctx.Process(
        target=networking_proc_fn,
        args=(chain_config, pool_class),
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
def run_database_process(chain_config: ChainConfig, db_class: Type[LevelDB]) -> None:
    db = db_class(db_path=chain_config.database_dir)

    serve_chaindb(chain_config, db)


def create_dbmanager(ipc_path: str) -> BaseManager:
    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', proxytype=DBProxy)  # type: ignore
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)  # type: ignore
    DBManager.register('get_chain', proxytype=ChainProxy)  # type: ignore

    manager = DBManager(address=ipc_path)  # type: ignore
    manager.connect()  # type: ignore
    return manager


@with_queued_logging
def run_lightnode_process(
        chain_config: ChainConfig,
        pool_class: Type[HardCodedNodesPeerPool]) -> None:

    manager = create_dbmanager(chain_config.database_ipc_path)
    chaindb = manager.get_chaindb()  # type: ignore

    if chain_config.network_id == MAINNET_NETWORK_ID:
        chain_class = MainnetLightChain  # type: ignore
    elif chain_config.network_id == ROPSTEN_NETWORK_ID:
        chain_class = RopstenLightChain  # type: ignore
    else:
        raise NotImplementedError(
            "Only the mainnet and ropsten chains are currently supported"
        )
    peer_pool = pool_class(LESPeer, chaindb, chain_config.network_id, chain_config.nodekey)
    chain = chain_class(chaindb, peer_pool)

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
            await chain.peer_pool.stop()
            await chain.stop()

    loop.run_until_complete(run_chain(chain))
    loop.close()


@with_queued_logging
def run_fullnode_process(
        chain_config: ChainConfig,
        pool_class: Type[HardCodedNodesPeerPool]) -> None:

    manager = create_dbmanager(chain_config.database_ipc_path)
    db = manager.get_db()  # type: ignore
    chaindb = manager.get_chaindb()  # type: ignore
    chain = manager.get_chain()  # type: ignore

    peer_pool = pool_class(ETHPeer, chaindb, chain_config.network_id, chain_config.nodekey)
    asyncio.ensure_future(peer_pool.run())
    syncer = FullNodeSyncer(chain, chaindb, db, peer_pool)

    loop = asyncio.get_event_loop()
    # Use a ProcessPoolExecutor as the default so that we can offload cpu-intensive tasks from the
    # main thread.
    loop.set_default_executor(ProcessPoolExecutor())
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, syncer.cancel_token.trigger)

    async def run_syncer():
        try:
            await syncer.run()
        except OperationCancelled:
            pass
        finally:
            await peer_pool.stop()
            await syncer.stop()

    loop.run_until_complete(run_syncer())
    loop.close()
