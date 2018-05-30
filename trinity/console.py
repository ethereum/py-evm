import code
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Dict,
)

from cytoolz import merge

import web3


DEFAULT_BANNER: str = (
    "Trinity Console\n"
    "---------------\n"
    "An instance of Web3 connected to the running chain is available as the "
    "`w3` variable\n"
)


def ipython_shell(namespace: Dict[str, Any], banner: str) -> Any:
    """Try to run IPython shell."""
    try:
        import IPython
    except ImportError:
        raise ImportError(
            "The IPython library is not available.  Make sure IPython is "
            "installed or re-run with --vanilla-shell"
        )

    return IPython.terminal.embed.InteractiveShellEmbed(
        user_ns=namespace,
        banner1=banner,
    )


def python_shell(namespace: Dict[str, Any], banner: str) -> Any:
    """Start a vanilla Python REPL shell."""
    try:
        import readline, rlcompleter  # noqa: F401, E401
    except ImportError:
        pass
    else:
        readline.parse_and_bind('tab: complete')

    shell = code.InteractiveConsole(namespace)
    return partial(shell.interact, banner=banner)


def console(ipc_path: Path,
            use_ipython: bool=True,
            env: Dict[str, Any]=None,
            banner: str=DEFAULT_BANNER) -> Any:
    """
    Method that starts the chain, setups the trinity CLI and register the
    cleanup function.
    """
    if env is None:
        env = {}

    # cast needed until https://github.com/ethereum/web3.py/issues/867 is fixed
    w3 = web3.Web3(web3.IPCProvider(str(ipc_path)))

    namespace = merge({'w3': w3}, env)

    if use_ipython:
        ipython_shell(namespace, banner)()
    else:
        python_shell(namespace, banner)()
