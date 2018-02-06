import argparse
import asyncio
import atexit
import logging
import sys

from evm.exceptions import CanonicalHeadNotFound

from trinity.__version__ import __version__
from trinity.chains import (
    is_chain_initialized,
    initialize_chain,
    get_chain_protocol_class,
)
from trinity.cli import console
from trinity.constants import (
    ROPSTEN,
    SYNC_LIGHT,
)
from trinity.utils.chains import (
    ChainConfig,
)
from trinity.utils.db import (
    get_chain_db,
)
from trinity.db.mp import (
    GET,
    SET,
    EXISTS,
    DELETE,
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


def chain_obj(chain_config, sync_mode):
    if not is_chain_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        chain_class = initialize_chain(chain_config, sync_mode=sync_mode)
    else:
        chain_class = get_chain_protocol_class(chain_config, sync_mode=sync_mode)

    chaindb = get_chain_db(chain_config.database_dir)
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # TODO: figure out amore appropriate error to raise here.
        raise ValueError('Chain not intiialized')

    return chain_class(chaindb)


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

    chain_config = ChainConfig.from_parser_args(chain_identifier, args)

    # if console command, run the trinity CLI
    if args.subcommand == 'console':
        use_ipython = not args.vanilla_shell
        debug = args.log_level.upper() == 'DEBUG'

        chain = chain_obj(chain_config, sync_mode)
        args.func(chain, use_ipython=use_ipython, debug=debug)
        sys.exit(0)

    logger, log_queue, listener = setup_trinity_logging(args.log_level.upper())

    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    db_process_pipe, db_connection_pipe = ctx.Pipe()

    # For now we just run the light sync against ropsten by default.
    chain_process = ctx.Process(
        target=run_chain,
        args=(chain_config, sync_mode, db_connection_pipe),
        kwargs={'log_queue': log_queue}
    )
    db_process = ctx.Process(
        target=base_db_process,
        args=(
            'evm.db.backends.level.LevelDB',
            {'db_path': chain_config.database_dir},
            db_process_pipe,
        ),
        kwargs={'log_queue': log_queue}
    )

    try:
        db_process.start()
        chain_process.start()
        chain_process.join()
    except KeyboardInterrupt:
        logger.info('Keyboard Interrupt: Stopping')
        chain_process.terminate()
        db_process.terminate()


@with_queued_logging
def base_db_process(db_class_path, db_init_kwargs, mp_pipe, log_queue):
    db = get_chain_db(db_class_path, **db_init_kwargs)
    logger = logging.getLogger('trinity.main.db_process')

    logger.info('Starting DB Process')
    while True:
        try:
            request = mp_pipe.recv()
        except EOFError as err:
            logger.info('Breaking out of loop: %s', err)
            break

        req_id, method, *params = request

        if method == GET:
            key = params[0]
            logger.debug('GET: %s', key)

            try:
                mp_pipe.send([req_id, db.get(key)])
            except KeyError as err:
                mp_pipe.send([req_id, err])
        elif method == SET:
            key, value = params
            logger.debug('SET: %s -> %s', key, value)
            try:
                mp_pipe.send([req_id, db.set(key, value)])
            except KeyError as err:
                mp_pipe.send([req_id, err])
        elif method == EXISTS:
            key = params[0]
            logger.debug('EXISTS: %s', key)
            try:
                mp_pipe.send([req_id, db.exists(key)])
            except KeyError as err:
                mp_pipe.send([req_id, err])
        elif method == DELETE:
            key = params[0]
            logger.debug('DELETE: %s', key)
            try:
                mp_pipe.send([req_id, db.delete(key)])
            except KeyError as err:
                mp_pipe.send([req_id, err])
        else:
            logger.error("Got unknown method: %s: %s", method, params)
            raise Exception('Invalid request method')


@with_queued_logging
def run_chain(chain_config, sync_mode, db_pipe):
    if not is_chain_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        chain_class = initialize_chain(chain_config, sync_mode=sync_mode)
    else:
        chain_class = get_chain_protocol_class(chain_config, sync_mode=sync_mode)

    chaindb = get_chain_db('trinity.db.mp.MPDB', init_kwargs={'mp_pipe': db_pipe})
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # TODO: figure out a more appropriate error to raise here.
        raise ValueError('Chain not intiialized')

    chain = chain_class(chaindb)

    loop = asyncio.get_event_loop()

    loop.run_until_complete(chain.run())

    def cleanup():
        # This is to instruct chain.run() to exit, which will cause the event loop to stop.
        chain._should_stop.set()

        # The above was needed because the event loop stops when chain.run() returns and then
        # chain.stop() would never finish if we just ran it with run_coroutine_threadsafe().
        loop.run_until_complete(chain.stop())
        loop.close()

    atexit.register(cleanup)
