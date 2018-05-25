import os
from pathlib import Path

from eth_utils import (
    decode_hex,
    to_dict,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from .xdg import (
    get_xdg_trinity_root,
)


DEFAULT_DATA_DIRS = {
    ROPSTEN_NETWORK_ID: 'ropsten',
    MAINNET_NETWORK_ID: 'mainnet',
}


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str) -> Path:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return Path(os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(get_xdg_trinity_root(), chain_name),
    ))


def get_data_dir_for_network_id(network_id: int) -> Path:
    """
    Returns the data directory for the chain associated with the given network
    id.  If the network id is unknown, raises a KeyError.
    """
    try:
        return get_local_data_dir(DEFAULT_DATA_DIRS[network_id])
    except KeyError:
        raise KeyError("Unknown network id: `{0}`".format(network_id))


LOG_DIRNAME = 'logs'
LOG_FILENAME = 'trinity.log'


def get_logfile_path(data_dir: Path) -> Path:
    """
    Returns the path to the log files.
    """
    return data_dir / LOG_DIRNAME / LOG_FILENAME


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return Path(os.environ.get(
        'TRINITY_NODEKEY',
        str(data_dir / NODEKEY_FILENAME),
    ))


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'TRINITY_DATABASE_IPC',
        data_dir / DATABASE_SOCKET_FILENAME,
    ))


JSONRPC_SOCKET_FILENAME = 'jsonrpc.ipc'


def get_jsonrpc_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the ipc socket for the JSON-RPC server.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'TRINITY_JSONRPC_IPC',
        data_dir / JSONRPC_SOCKET_FILENAME,
    ))


#
# Nodekey loading
#
def load_nodekey(nodekey_path: Path) -> PrivateKey:
    with nodekey_path.open('rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


@to_dict
def construct_chain_config_params(args):
    """
    Helper function for constructing the kwargs to initialize a ChainConfig object.
    """
    yield 'network_id', args.network_id

    if args.data_dir is not None:
        yield 'data_dir', args.data_dir

    if args.nodekey_path and args.nodekey:
        raise ValueError("Cannot provide both nodekey_path and nodekey")
    elif args.nodekey_path is not None:
        yield 'nodekey_path', args.nodekey_path
    elif args.nodekey is not None:
        yield 'nodekey', decode_hex(args.nodekey)

    if args.sync_mode is not None:
        yield 'sync_mode', args.sync_mode

    if args.port is not None:
        yield 'port', args.port

    if args.preferred_nodes is None:
        yield 'preferred_nodes', args.preferred_nodes
    else:
        yield 'preferred_nodes', tuple(args.preferred_nodes)
