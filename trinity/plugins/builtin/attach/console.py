import code
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Dict,
)

from eth_utils import encode_hex
from eth_utils.toolz import merge

from eth.db.chain import ChainDB
from eth.db.backends.level import LevelDB

from trinity._utils.log_messages import (
    create_missing_ipc_error_message,
)
from trinity.config import (
    TrinityConfig,
)


DEFAULT_BANNER: str = (
    "Trinity Console\n"
    "---------------\n"
    "An instance of Web3 connected to the running chain is available as the "
    "`w3` variable\n"
    "The exposed `rpc` function allows raw RPC API calls (e.g. rpc('net_listening'))\n"
)

DB_SHELL_BANNER: str = (
    "Trinity DB Shell\n"
    "---------------\n"
    "An instance of `ChainDB` connected to the database is available as the "
    "`chaindb` variable\n"
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
            banner: str=DEFAULT_BANNER) -> None:
    """
    Method that starts the chain, setups the trinity CLI and register the
    cleanup function.
    """
    if env is None:
        env = {}

    # if ipc_path is not found, raise an exception with a useful message
    if not ipc_path.exists():
        raise FileNotFoundError(create_missing_ipc_error_message(ipc_path))

    # wait to import web3, because it's somewhat large, and not usually used
    import web3
    ipc_provider = web3.IPCProvider(ipc_path)
    w3 = web3.Web3(ipc_provider)

    # Allow omitting params by defaulting to `None`
    def rpc(method: str, params: Dict[str, Any] = None) -> str:
        return ipc_provider.make_request(method, params)

    namespace = merge({'w3': w3, 'rpc': rpc}, env)

    shell(use_ipython, namespace, banner)


def db_shell(use_ipython: bool, database_dir: Path, trinity_config: TrinityConfig) -> None:

    db = LevelDB(database_dir)
    chaindb = ChainDB(db)
    head = chaindb.get_canonical_head()
    chain_config = trinity_config.get_chain_config()
    chain = chain_config.full_chain_class(db)

    greeter = f"""
    Head: #{head.block_number}
    Hash: {head.hex_hash}
    State Root: {encode_hex(head.state_root)}

    Available Context Variables:
      - `db`: base database object
      - `chaindb`: `ChainDB` instance
      - `trinity_config`: `TrinityConfig` instance
      - `chain_config`: `ChainConfig` instance
      - `chain`: `Chain` instance
    """

    namespace = {
        'db': db,
        'chaindb': chaindb,
        'trinity_config': trinity_config,
        'chain_config': chain_config,
        'chain': chain,
    }
    shell(use_ipython, namespace, DB_SHELL_BANNER + greeter)


def shell(use_ipython: bool, namespace: Dict[str, Any], banner: str) -> None:
    if use_ipython:
        ipython_shell(namespace, banner)()
    else:
        python_shell(namespace, banner)()
