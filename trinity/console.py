import asyncio
import logging

from cytoolz import merge

import web3


LOGFILE = '/tmp/trinity-shell.log'
LOGLEVEL = logging.INFO

loop = asyncio.get_event_loop()


DEFAULT_BANNER = (
    "Trinity Console\n"
    "---------------\n"
    "An instance of Web3 connected to the running chain is available as the "
    "`w3` variable\n"
)


def ipython_shell(namespace, banner):
    """Try to run IPython shell."""
    try:
        import IPython  # noqa: F401
    except ImportError:
        raise ImportError(
            "The IPython library is not available.  Make sure IPython is "
            "installed or re-run with --vanilla-shell"
        )

    from IPython.terminal.embed import InteractiveShellEmbed

    return InteractiveShellEmbed(user_ns=namespace, banner1=banner)


def python_shell(namespace, banner):
    """Start a vanilla Python REPL shell."""
    import code
    from functools import partial

    try:
        import readline, rlcompleter  # noqa: F401, E401
    except ImportError:
        pass
    else:
        readline.parse_and_bind('tab: complete')

    shell = code.InteractiveConsole(namespace)
    return partial(shell.interact, banner=banner)


def console(ipc_path,
            use_ipython=True,
            env=None,
            banner=DEFAULT_BANNER):
    """
    Method that starts the chain, setups the trinity CLI and register the
    cleanup function.
    """
    if env is None:
        env = {}

    w3 = web3.Web3(web3.IPCProvider(ipc_path))

    namespace = merge({'w3': w3}, env)

    if use_ipython:
        shell = ipython_shell(namespace, banner)
    else:
        shell = python_shell(namespace, banner)

    shell()
