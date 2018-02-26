import asyncio
import atexit
import logging
import traceback
import threading
from typing import Dict  # noqa: F401

from p2p.lightchain import LightChain


LOGFILE = '/tmp/trinity-shell.log'
LOGLEVEL = logging.INFO

loop = asyncio.get_event_loop()


def wait_for_result(coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    return future.result()


def setup_namespace(chain):
    """Setup the variables to be used in shell instance."""

    namespace = dict(
        chain=chain,
        wait_for_result=wait_for_result
    )
    return namespace


def ipython_shell(namespace=None, banner=None, debug=False):
    """Try to run IPython shell."""
    try:
        import IPython
    except ImportError:
        if debug:
            traceback.print_exc()
        print("IPython not available. Running default shell...")
        return
    # First try newer(IPython >=1.0) top `IPython` level import
    if hasattr(IPython, 'terminal'):
        from IPython.terminal.embed import InteractiveShellEmbed
        kwargs = dict(user_ns=namespace)
    else:
        from IPython.frontend.terminal.embed import InteractiveShellEmbed  # type: ignore
        kwargs = dict(user_ns=namespace)
    if banner:
        kwargs = dict(banner1=banner)
    return InteractiveShellEmbed(**kwargs)


def python_shell(namespace=None, banner=None, debug=False):
    """Start a vanilla Python REPL shell."""
    import code
    from functools import partial
    try:
        import readline, rlcompleter    # NOQA
    except ImportError:
        if debug:
            traceback.print_exc()
    else:
        readline.parse_and_bind('tab: complete')
    # Add global, local and custom namespaces to current shell
    default_ns = globals().copy()
    default_ns.update(locals())
    if namespace:
        default_ns.update(namespace)
    # Configure kwargs to pass banner
    kwargs = dict()  # type: Dict[str, str]
    if banner:
        kwargs = dict(banner=banner)
    shell = code.InteractiveConsole(default_ns)
    return partial(shell.interact, **kwargs)


def console(
        chain: LightChain,
        use_ipython: bool = True,
        namespace: dict = None,
        banner: str = None,
        debug: bool = False) -> None:
    """
    Method that starts the chain, setups the trinity CLI and register the
    cleanup function.
    """
    # update the namespace with the required variables
    namespace = {} if namespace is None else namespace
    namespace.update(setup_namespace(chain))

    if use_ipython:
        shell = ipython_shell(namespace, banner, debug)

    print("Logging to", LOGFILE)
    log_level = logging.DEBUG if debug else LOGLEVEL
    logging.basicConfig(level=log_level, filename=LOGFILE)

    # Start the thread
    t = threading.Thread(target=loop.run_until_complete, args=(run_lightchain(chain),),
                         daemon=True)
    t.start()

    # If can't import or start the IPython shell, use the default shell
    if not use_ipython or shell is None:
        shell = python_shell(namespace, banner, debug)
    shell()

    def cleanup():
        chain.cancel_token.trigger()
        # Wait until run() finishes.
        t.join()

    atexit.register(cleanup)


async def run_lightchain(lightchain: LightChain) -> None:

    try:
        asyncio.ensure_future(lightchain.peer_pool.run())
        await lightchain.run()
    finally:
        await lightchain.peer_pool.stop()
        await lightchain.stop()
