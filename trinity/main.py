import asyncio
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

from p2p.peer import (
    LESPeer,
    HardCodedNodesPeerPool,
)

from trinity.chains import (
    get_chain_protocol_class,
    initialize_data_dir,
    initialize_database,
    is_data_dir_initialized,
    is_database_initialized,
    serve_chaindb,
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

    logger, log_queue, listener = setup_trinity_logging(args.log_level.upper())

    if args.network_id not in PRECONFIGURED_NETWORKS:
        raise NotImplementedError(
            "Unsupported network id: {0}.  Only the ropsten and mainnet "
            "networks are supported.".format(args.network_id)
        )

    if args.sync_mode != SYNC_LIGHT:
        raise NotImplementedError(
            "Only light sync is supported.  Run with `--sync-mode=light` or `--light`"
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

    # First initialize the database process.
    database_server_process = ctx.Process(
        target=run_database_process,
        args=(
            chain_config,
            LevelDB,
        ),
        kwargs={'log_queue': log_queue}
    )

    # For now we just run the light sync against ropsten by default.
    networking_process = ctx.Process(
        target=run_networking_process,
        args=(chain_config, args.sync_mode, pool_class),
        kwargs={'log_queue': log_queue}
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

    serve_chaindb(db, chain_config.database_ipc_path)


@with_queued_logging
def run_networking_process(
        chain_config: ChainConfig,
        sync_mode: str,
        pool_class: Type[HardCodedNodesPeerPool]) -> None:

    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', proxytype=DBProxy)  # type: ignore
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)  # type: ignore

    manager = DBManager(address=chain_config.database_ipc_path)  # type: ignore
    manager.connect()  # type: ignore

    chaindb = manager.get_chaindb()  # type: ignore

    if not is_database_initialized(chaindb):
        initialize_database(chain_config, chaindb)

    chain_class = get_chain_protocol_class(chain_config, sync_mode=sync_mode)
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
