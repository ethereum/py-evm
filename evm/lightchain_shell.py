"""
Run a LightChain (on Ropsten) in a separate thread, allowing users to interact
with it via the python interpreter running on the main thread.

See docs/quickstart.rst for more info on how to use this.
"""
import argparse
import asyncio
import atexit
import threading

from evm.db.chain import BaseChainDB
from evm.chains.ropsten import ROPSTEN_NETWORK_ID
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.p2p import ecies
from evm.p2p.lightchain import LightChain
from evm.db.backends.level import LevelDB


parser = argparse.ArgumentParser()
parser.add_argument('-db', type=str, required=True)
args = parser.parse_args()

DemoLightChain = LightChain.configure(
    name='Demo LightChain',
    privkey=ecies.generate_privkey(),
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
)


chain = DemoLightChain(BaseChainDB(LevelDB(args.db)))
loop = asyncio.get_event_loop()
t = threading.Thread(target=loop.run_until_complete, args=(chain.run(),))
t.setDaemon(True)
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
