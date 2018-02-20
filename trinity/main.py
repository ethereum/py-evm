import argparse
import asyncio
import atexit
from multiprocessing.managers import (
    BaseManager,
)
import sys

from evm.db.backends.level import LevelDB
from evm.db.chain import ChainDB

from evm.p2p.peer import (
    LESPeer,
    PeerPool,
)

from trinity.__version__ import __version__
from trinity.chains import (
    get_chain_protocol_class,
    initialize_data_dir,
    initialize_database,
    is_data_dir_initialized,
    is_database_initialized,
    serve_chaindb,
)
from trinity.cli import console
from trinity.constants import (
    ROPSTEN,
    SYNC_LIGHT,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
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


DEFAULT_LOG_LEVEL = 'info'
LOG_LEVEL_CHOICES = (
    'debug',
    'info',
)


parser = argparse.ArgumentParser(description='Trinity')

# enable `trinity --version`
parser.add_argument('--version', action='version', version=__version__)

# set global logging level
parser.add_argument(
    '-l',
    '--log-level',
    choices=LOG_LEVEL_CHOICES,
    default=DEFAULT_LOG_LEVEL,
    help="Sets the logging level",
)

# options for running chains
parser.add_argument(
    '--ropsten',
    action='store_true',
    help="Ropsten network: pre configured proof-of-work test network",
)
parser.add_argument(
    '--light',  # TODO: consider --sync-mode like geth.
    action='store_true',
)
parser.add_argument(
    '--trinity-root-dir',
    help=(
        "The filesystem path to the base directory that trinity will store it's "
        "information.  Default: $XDG_DATA_HOME/.local/share/trinity"
    ),
)
parser.add_argument(
    '--data-dir',
    help=(
        "The directory where chain data is stored"
    ),
)
parser.add_argument(
    '--nodekey',
    help=(
        "Hexadecimal encoded private key to use for the nodekey"
    )
)
parser.add_argument(
    '--nodekey-path',
    help=(
        "The filesystem path to the file which contains the nodekey"
    )
)

# Add console sub-command to trinity CLI.
subparser = parser.add_subparsers(dest='subcommand')
console_parser = subparser.add_parser('console', help='start the trinity REPL')
console_parser.add_argument(
    '--vanilla-shell',
    action='store_true',
    default=False,
    help='start a native Python shell'
)
console_parser.set_defaults(func=console)


def main():
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

    # if console command, run the trinity CLI
    if args.subcommand == 'console':
        use_ipython = not args.vanilla_shell
        debug = args.log_level.upper() == 'DEBUG'

        # TODO: this should use the base `Chain` class rather than the protocol
        # class since it's just a repl with access to the chain.
        chain_class = get_chain_protocol_class(chain_config, sync_mode)
        chaindb = ChainDB(LevelDB(chain_config.database_dir))
        peer_pool = PeerPool(LESPeer, chaindb, chain_config.network_id, chain_config.nodekey)

        chain = chain_class(chaindb, peer_pool)
        args.func(chain, use_ipython=use_ipython, debug=debug)
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
        args=(chain_config, sync_mode),
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
def run_database_process(chain_config, db_class):
    db = db_class(db_path=chain_config.database_dir)

    serve_chaindb(db, chain_config.database_ipc_path)


@with_queued_logging
def run_networking_process(chain_config, sync_mode):
    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=DBProxy)
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)

    manager = DBManager(address=chain_config.database_ipc_path)
    manager.connect()

    chaindb = manager.get_chaindb()

    if not is_data_dir_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        initialize_data_dir(chain_config)

    if not is_database_initialized(chaindb):
        initialize_database(chain_config, chaindb)

    chain_class = get_chain_protocol_class(chain_config, sync_mode=sync_mode)
    peer_pool = PeerPool(LESPeer, chaindb, chain_config.network_id, chain_config.nodekey)

    async def run():
        try:
            asyncio.ensure_future(peer_pool.run())
            # chain.run() will run in a loop until our atexit handler is called, at which point it returns
            # and we cleanly stop the pool and chain.
            await chain.run()
        finally:
            await peer_pool.stop()
            await chain.stop()

    chain = chain_class(chaindb, peer_pool)

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass

    def cleanup():
        # This is to instruct chain.run() to exit, which will cause the event loop to stop.
        chain._should_stop.set()

        loop.close()

    atexit.register(cleanup)
