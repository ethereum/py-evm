import argparse
import asyncio
import atexit
import os

from evm.exceptions import CanonicalHeadNotFound

from trinity.__version__ import __version__
from trinity.chains import (
    is_chain_initialized,
    initialize_chain,
    get_chain_protocol_class,
    construct_chain_config_params,
)
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
    '--base-dir',
)
parser.add_argument(
    '--data-dir',
)
parser.add_argument(
    '--nodekey',
)
parser.add_argument(
    '--nodekey-path',
)


def main():
    args = parser.parse_args()

    logger, log_queue, listener = setup_trinity_logging(args.log_level.upper())

    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

<<<<<<< HEAD
    db_path = get_data_dir(ROPSTEN)
    os.makedirs(db_path, exist_ok=True)
=======
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

    chain_config_params = construct_chain_config_params(args)
    chain_config = ChainConfig(chain_identifier, **chain_config_params)
>>>>>>> Chain initialization and CLI args for chain params.

    # For now we just run the light sync against ropsten by default.
    process = ctx.Process(
        target=run_chain,
        args=(chain_config, sync_mode),
        kwargs={'log_queue': log_queue}
    )

    try:
        process.start()
        process.join()
    except KeyboardInterrupt:
        logger.info('Keyboard Interrupt: Stopping')
        process.terminate()


@with_queued_logging
def run_chain(chain_config, sync_mode):
    if not is_chain_initialized(chain_config):
        # TODO: this will only work as is for chains with known genesis
        # parameters.  Need to flesh out how genesis parameters for custom
        # chains are defined and passed around.
        chain_class = initialize_chain(chain_config, sync_mode=sync_mode)
    else:
        chain_class = get_chain_protocol_class(chain_config, sync_mode=sync_mode)

    # TODO: this should probably be something that is passed in to allow
    # specifying the db_path via the CLI as well as the db class.
    chaindb = get_chain_db(chain_config.data_dir)
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # TODO: figure out amore appropriate error to raise here.
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
