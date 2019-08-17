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

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.operations.attestation_pool import AttestationPool

from trinity.config import (
    Eth1AppConfig,
    BeaconAppConfig,
    TrinityConfig,
)
from trinity.db.manager import DBClient
from trinity._utils.log_messages import (
    create_missing_ipc_error_message,
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


def db_shell(use_ipython: bool, config: Dict[str, str]) -> None:
    greeter = """
    Head: #%(block_number)s
    Hash: %(hex_hash)s
    State Root: %(state_root_hex)s
    Inspecting active Trinity? %(trinity_already_running)s

    Available Context Variables:
      - `db`: base database object
      - `chaindb`: `ChainDB` instance
      - `trinity_config`: `TrinityConfig` instance
      - `chain_config`: `ChainConfig` instance
      - `chain`: `Chain` instance
    """ % config

    namespace = {
        'db': config.get("db"),
        'chaindb': config.get("chaindb"),
        'trinity_config': config.get("trinity_config"),
        'chain_config': config.get("chain_config"),
        'chain': config.get("chain"),
    }
    shell(use_ipython, namespace, DB_SHELL_BANNER + greeter)


def get_eth1_shell_context(database_dir: Path, trinity_config: TrinityConfig) -> Dict[str, Any]:
    app_config = trinity_config.get_app_config(Eth1AppConfig)
    ipc_path = trinity_config.database_ipc_path

    trinity_already_running = ipc_path.exists()
    if trinity_already_running:
        db = DBClient.connect(ipc_path)
    else:
        db = LevelDB(database_dir)

    chaindb = ChainDB(db)
    head = chaindb.get_canonical_head()
    chain_config = app_config.get_chain_config()
    chain = chain_config.full_chain_class(db)
    return {
        'db': db,
        'chaindb': chaindb,
        'trinity_config': trinity_config,
        'chain_config': chain_config,
        'chain': chain,
        'block_number': head.block_number,
        'hex_hash': head.hex_hash,
        'state_root_hex': encode_hex(head.state_root),
        'trinity_already_running': trinity_already_running,
    }


def get_beacon_shell_context(database_dir: Path, trinity_config: TrinityConfig) -> Dict[str, Any]:
    app_config = trinity_config.get_app_config(BeaconAppConfig)

    ipc_path = trinity_config.database_ipc_path

    trinity_already_running = ipc_path.exists()
    if trinity_already_running:
        db = DBClient.connect(ipc_path)
    else:
        db = LevelDB(database_dir)

    chain_config = app_config.get_chain_config()
    chain = chain_config.beacon_chain_class
    attestation_pool = AttestationPool()
    chain = chain_config.beacon_chain_class(
        db,
        attestation_pool,
        chain_config.genesis_config
    )

    chaindb = BeaconChainDB(db, chain_config.genesis_config)
    head = chaindb.get_canonical_head(BeaconBlock)
    return {
        'db': db,
        'chaindb': chaindb,
        'trinity_config': trinity_config,
        'chain_config': chain_config,
        'chain': chain,
        'block_number': head.slot,
        'hex_hash': head.hash_tree_root.hex(),
        'state_root_hex': encode_hex(head.state_root),
        'trinity_already_running': trinity_already_running
    }


def shell(use_ipython: bool, namespace: Dict[str, Any], banner: str) -> None:
    if use_ipython:
        ipython_shell(namespace, banner)()
    else:
        python_shell(namespace, banner)()
