import argparse
import asyncio
import atexit

from evm.p2p.lightchain import LightChain
from evm.db.backends.level import LevelDB

from trinity.constants import (
    ROPSTEN,
)
from trinity.utils.filesystem import (
    ensure_path_exists,
)
from trinity.utils.logging import (
    setup_trinity_logging,
    setup_queue_logging,
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.xdg import (
    get_data_dir,
)


DEFAULT_LOG_LEVEL = 'info'
LOG_LEVEL_CHOICES = (
    'debug',
    'info',
)


parser = argparse.ArgumentParser(description='Trinity')
parser.add_argument(
    '-l',
    '--log-level',
    choices=LOG_LEVEL_CHOICES,
    default=DEFAULT_LOG_LEVEL,
)
parse.add_argument(
    '--ropsten',
    action='store_true',
)


def main():
    args = parser.parse_args()

    logger, log_queue, listener = setup_trinity_logging(args.log_level.upper())

    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    db_path = get_data_dir(ROPSTEN)
    ensure_path_exists(db_path)

    # For now we just run the light sync against ropsten by default.
    process = ctx.Process(
        target=ropsten_light_node_sync,
        args=(log_queue, db_path),
    )

    try:
        process.start()
        process.join()
    except KeyboardInterrupt:
        logger.info('Keyboard Interrupt: Stopping')
        process.terminate()


def ropsten_light_node_sync(log_queue, db_path):
    """
    Runs an LES node against the Ropsten network.
    """
    setup_queue_logging(log_queue)

    chaindb = BaseChainDB(LevelDB(db_path))
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = DemoLightChain.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)
    else:
        # We're reusing an existing db.
        chain = DemoLightChain(chaindb)

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
