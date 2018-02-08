"""
Run a LightChain (on Ropsten) in a separate thread, allowing users to interact
with it via the python interpreter running on the main thread.

See docs/quickstart.rst for more info on how to use this.
"""
import argparse
import asyncio
import atexit
import logging
import threading

from evm.db.chain import ChainDB
from evm.exceptions import CanonicalHeadNotFound
from evm.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_NETWORK_ID,
)
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.p2p import ecies
from evm.p2p.lightchain import LightChain
from evm.p2p.peer import (
    LESPeer,
    PeerPool,
)
from evm.db.backends.level import LevelDB


LOGFILE = '/tmp/lightchain-shell.log'
LOGLEVEL = logging.INFO

parser = argparse.ArgumentParser()
parser.add_argument('-db', type=str, required=True)
parser.add_argument('-debug', action='store_true')
args = parser.parse_args()

print("Logging to", LOGFILE)
if args.debug:
    LOGLEVEL = logging.DEBUG
logging.basicConfig(level=LOGLEVEL, filename=LOGFILE)

DemoLightChain = LightChain.configure(
    name='Demo LightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
)

chaindb = ChainDB(LevelDB(args.db))
peer_pool = PeerPool(LESPeer, chaindb, ROPSTEN_NETWORK_ID, ecies.generate_privkey())
try:
    chaindb.get_canonical_head()
except CanonicalHeadNotFound:
    # We're starting with a fresh DB.
    chain = DemoLightChain.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER, peer_pool)
else:
    # We're reusing an existing db.
    chain = DemoLightChain(chaindb, peer_pool)


async def run():
    asyncio.ensure_future(peer_pool.run())
    # chain.run() will run in a loop until our atexit handler is called, at which point it returns
    # and we cleanly stop the pool and chain.
    await chain.run()
    await peer_pool.stop()
    await chain.stop()


loop = asyncio.get_event_loop()
t = threading.Thread(target=loop.run_until_complete, args=(run(),), daemon=True)
t.start()


def wait_for_result(coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    return future.result()


def cleanup():
    chain._should_stop.set()
    # Wait until run() finishes.
    t.join()


atexit.register(cleanup)
