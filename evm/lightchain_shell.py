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

from evm.db.chain import BaseChainDB
from evm.exceptions import CanonicalHeadNotFound
from evm.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_NETWORK_ID,
)
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.p2p import ecies
from evm.p2p.lightchain import LightChain
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
    privkey=ecies.generate_privkey(),
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
)

chaindb = BaseChainDB(LevelDB(args.db))
try:
    chaindb.get_canonical_head()
except CanonicalHeadNotFound:
    # We're starting with a fresh DB.
    chain = DemoLightChain.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)
else:
    # We're reusing an existing db.
    chain = DemoLightChain(chaindb)

loop = asyncio.get_event_loop()
t = threading.Thread(target=loop.run_until_complete, args=(chain.run(),), daemon=True)
t.start()


def wait_for_result(coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    return future.result()


def cleanup():
    # This is to instruct chain.run() to exit, which will cause the event loop to stop.
    chain._should_stop.set()
    # This will block until the event loop has stopped.
    t.join()
    # The above was needed because the event loop stops when chain.run() returns and then
    # chain.stop() would never finish if we just ran it with run_coroutine_threadsafe().
    loop.run_until_complete(chain.stop())
    loop.close()


atexit.register(cleanup)
