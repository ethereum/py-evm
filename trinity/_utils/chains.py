import argparse
import os
from pathlib import Path
from typing import (
    cast,
    Any,
    Dict,
    Iterable,
    Optional,
    Tuple,
    Union,
)

from mypy_extensions import (
    TypedDict,
)

from eth_utils import (
    decode_hex,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from p2p.constants import DEFAULT_MAX_PEERS
from p2p.kademlia import Node as KademliaNode

from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
    SYNC_LIGHT,
)


DEFAULT_DATA_DIRS = {
    ROPSTEN_NETWORK_ID: 'ropsten',
    MAINNET_NETWORK_ID: 'mainnet',
}


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str, trinity_root_dir: Path) -> Path:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    try:
        return Path(os.environ['TRINITY_DATA_DIR'])
    except KeyError:
        return trinity_root_dir / chain_name


def get_data_dir_for_network_id(network_id: int, trinity_root_dir: Path) -> Path:
    """
    Returns the data directory for the chain associated with the given network
    id.  If the network id is unknown, raises a KeyError.
    """
    try:
        return get_local_data_dir(DEFAULT_DATA_DIRS[network_id], trinity_root_dir)
    except KeyError:
        raise KeyError(f"Unknown network id: `{network_id}`")


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


class TrinityConfigParams(TypedDict):
    network_id: int
    use_discv5: bool

    trinity_root_dir: Optional[str]

    genesis_config: Optional[Dict[str, Any]]

    data_dir: Optional[str]

    nodekey_path: Optional[str]
    nodekey: Optional[PrivateKey]

    max_peers: Optional[int]

    port: Optional[int]

    preferred_nodes: Optional[Tuple[KademliaNode, ...]]


def construct_trinity_config_params(
        args: argparse.Namespace) -> TrinityConfigParams:
    return cast(TrinityConfigParams, dict(_construct_trinity_config_params(args)))


def _construct_trinity_config_params(
        args: argparse.Namespace) -> Iterable[Tuple[str, Union[int, str, bytes, Tuple[str, ...]]]]:
    """
    Helper function for constructing the kwargs to initialize a TrinityConfig object.
    """
    yield 'network_id', args.network_id
    yield 'use_discv5', args.discv5

    if args.trinity_root_dir is not None:
        yield 'trinity_root_dir', args.trinity_root_dir

    if args.genesis is not None:
        if args.data_dir is None:
            raise ValueError("When providing a custom genesis, must also provide a data-dir")
        yield 'genesis_config', args.genesis

    if args.data_dir is not None:
        yield 'data_dir', args.data_dir

    if args.nodekey is not None:
        if os.path.isfile(args.nodekey):
            yield 'nodekey_path', args.nodekey
        else:
            yield 'nodekey', decode_hex(args.nodekey)

    if args.max_peers is not None:
        yield 'max_peers', args.max_peers
    # FIXME: This part of the code base should not know about `sync_mode`
    elif "sync_mode" in args:
        yield 'max_peers', _default_max_peers(args.sync_mode)
    else:
        yield 'max_peers', DEFAULT_MAX_PEERS

    if args.port is not None:
        yield 'port', args.port

    if args.preferred_nodes is None:
        yield 'preferred_nodes', tuple()
    else:
        yield 'preferred_nodes', tuple(args.preferred_nodes)


def _default_max_peers(sync_mode: str) -> int:
    if sync_mode == SYNC_LIGHT:
        return DEFAULT_MAX_PEERS // 2
    else:
        return DEFAULT_MAX_PEERS
