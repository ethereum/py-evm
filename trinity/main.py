import asyncio
from multiprocessing.managers import (
    BaseManager,
)
import signal
import sys
from typing import Type

from evm.db.backends.level import LevelDB

from p2p.peer import (
    LESPeer,
    PeerPool,
)

from trinity.chains import (
    get_chain_protocol_class,
    initialize_data_dir,
    initialize_database,
    is_data_dir_initialized,
    is_database_initialized,
    serve_chaindb,
)
from trinity.cli import (
    console,
    run_lightchain,
)
from trinity.constants import (
    ROPSTEN,
    SYNC_LIGHT,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.cli_parser import (
    parser,
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

from tests.p2p.integration_test_helpers import FakeAsyncChainDB, LocalGethPeerPool


def main() -> None:
    args = parser.parse_args()

    if args.ropsten:
        chain_identifier = ROPSTEN
    else:
        # TODO: mainnet
        chain_identifier = ROPSTEN

    if args.light:
        sync_mode = SYNC_LIGHT
    else:
        # TODO: actually use args.sync_mode (--sync-mode)
        sync_mode = SYNC_LIGHT

    chain_config = ChainConfig.from_parser_args(
        chain_identifier,
        args,
    )

    if not is_data_dir_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        initialize_data_dir(chain_config)

    pool_class = PeerPool
    if args.local_geth:
        pool_class = LocalGethPeerPool

    # if console command, run the trinity CLI
    if args.subcommand == 'console':
        use_ipython = not args.vanilla_shell
        debug = args.log_level.upper() == 'DEBUG'

        # TODO: this should use the base `Chain` class rather than the protocol
        # class since it's just a repl with access to the chain.
        chain_class = get_chain_protocol_class(chain_config, sync_mode)
        chaindb = FakeAsyncChainDB(LevelDB(chain_config.database_dir))
        if not is_database_initialized(chaindb):
            initialize_database(chain_config, chaindb)
        peer_pool = pool_class(LESPeer, chaindb, chain_config.network_id, chain_config.nodekey)

        chain = chain_class(chaindb, peer_pool)
        console(chain, use_ipython=use_ipython, debug=debug)
        sys.exit(0)

    logger, log_queue, listener = setup_trinity_logging(args.log_level.upper())

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
        args=(chain_config, sync_mode, pool_class),
        kwargs={'log_queue': log_queue}
    )

    # start the processes
    database_server_process.start()
    wait_for_ipc(chain_config.database_ipc_path)

    networking_process.start()

    try:
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
        pool_class: Type[PeerPool]) -> None:

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

    loop.run_until_complete(run_lightchain(chain))
    loop.close()
