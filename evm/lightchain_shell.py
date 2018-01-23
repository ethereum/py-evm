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
import traceback

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
parser.add_argument('-default_shell', action='store_true', default=False)
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

# This is to start IPython or Python REPL.

def ipython_shell_1(namespace=None, banner=None, debug=False):
    """IPyhton v1.0 specific import"""
    try:
        from IPython.frontend.terminal.embed import InteractiveShellEmbed
    except ImportError:
        if debug:
            traceback.print_exc()
        return None
    kwargs = dict(user_ns=namespace)
    if banner:
        kwargs = dict(banner1=banner)
    return InteractiveShellEmbed.instance(**kwargs)


def ipython_shell(namespace=None, banner=None, debug=False):
    """IPython version > 1.0"""
    try:
        from IPython.terminal.embed import InteractiveShellEmbed
    except ImportError:
        if debug:
            traceback.print_exc()
        return None
    kwargs = dict(local_ns=namespace)
    if banner:
        kwargs = dict(banner1=banner)
    return InteractiveShellEmbed.instance(**kwargs)


def start_ipython_shell(namespace=None, banner=None, debug=False):
    """Trt to run IPython shell."""
    for shell_method in [ipython_shell, ipython_shell_1]:
        shell = shell_method(namespace, banner, debug)
        if shell is not None:
            shell()
            break
    else:
        print('IPython not installed.')
        return False


def start_python_shell(namespace=None, banner=None, debug=False):
    """Start a normal Python rlp shell."""
    import code
    try:
        import readline, rlcompleter
    except ImportError:
        if debug:
            traceback.print_exc()
    else:
        readline.parse_and_bind('tab: complete')
    # Add global, local and custome namespaces to current shell
    default_ns = globals().copy()
    default_ns.update(locals())
    if namespace:
        default_ns.update(namespace)
    # Configure kwargs to pass banner and exit message
    kwargs = dict()
    if banner:
        kwargs = dict(banner=banner)
    shell = code.InteractiveConsole(default_ns)
    shell.interact(**kwargs)


def start_shell(use_ipython=True, namespace=None, banner=None, debug=False):
    ip_shell_status = None
    if use_ipython:
        ip_shell_status = start_ipython_shell(namespace, banner, debug)
    # If can't import/start the ipython shell use the default shell
    if not use_ipython or ip_shell_status is False:
        start_python_shell(namespace, banner, debug)


banner = ''
use_ipython = not args.default_shell
start_shell(use_ipython=use_ipython, banner=banner, debug=args.debug)
