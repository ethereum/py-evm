import os
from typing import (
    Tuple,
    Union,
)

from pathlib import PurePath

from pathlib import PurePath

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

from p2p.kademlia import Node
from p2p.constants import (
    MAINNET_BOOTNODES,
    ROPSTEN_BOOTNODES,
)

from trinity.constants import (
    SYNC_FULL,
    SYNC_LIGHT,
)
from .xdg import (
    get_xdg_trinity_root,
)


DEFAULT_DATA_DIRS = {
    ROPSTEN_NETWORK_ID: 'ropsten',
    MAINNET_NETWORK_ID: 'mainnet',
}
DATABASE_DIR_NAME = 'chain'


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str) -> PurePath:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return PurePath(os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(get_xdg_trinity_root(), chain_name),
    ))


def get_data_dir_for_network_id(network_id: int) -> PurePath:
    """
    Returns the data directory for the chain associated with the given network
    id.  If the network id is unknown, raises a KeyError.
    """
    try:
        return get_local_data_dir(DEFAULT_DATA_DIRS[network_id])
    except KeyError:
        raise KeyError("Unknown network id: `{0}`".format(network_id))


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(data_dir: PurePath) -> PurePath:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return PurePath(os.environ.get(
        'TRINITY_NODEKEY',
        str(data_dir / NODEKEY_FILENAME),
    ))


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(data_dir: PurePath) -> str:
    """
    Returns the path to the private key used for devp2p connections.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'PurePath' objects correctly.
    """
    return os.environ.get(
        'TRINITY_DATABASE_IPC',
        os.path.join(str(data_dir), DATABASE_SOCKET_FILENAME),
    )


JSONRPC_SOCKET_FILENAME = 'jsonrpc.ipc'


def get_jsonrpc_socket_path(data_dir: PurePath) -> str:
    """
    Returns the path to the ipc socket for the JSON-RPC server.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'PurePath' objects correctly.
    """
    return os.environ.get(
        'TRINITY_JSONRPC_IPC',
        os.path.join(str(data_dir), JSONRPC_SOCKET_FILENAME),
    )


#
# Nodekey loading
#
def load_nodekey(nodekey_path: PurePath) -> PrivateKey:
    with open(str(nodekey_path), 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


class ChainConfig:
    _data_dir: PurePath = None
    _nodekey_path: PurePath = None
    _nodekey = None
    _network_id: int = None

    port: int = None

    bootstrap_nodes: Tuple[Node, ...] = None

    def __init__(self,
                 network_id: int,
                 data_dir: str=None,
                 nodekey_path: str=None,
                 nodekey: PrivateKey=None,
                 sync_mode: str=SYNC_FULL,
                 port: int=30303,
                 bootstrap_nodes: Tuple[Node, ...]=None) -> None:
        self.network_id = network_id
        self.sync_mode = sync_mode
        self.port = port

        if bootstrap_nodes is None:
            if self.network_id == MAINNET_NETWORK_ID:
                self.bootstrap_nodes = tuple(
                    Node.from_uri(enode) for enode in MAINNET_BOOTNODES
                )
            elif self.network_id == ROPSTEN_NETWORK_ID:
                self.bootstrap_nodes = tuple(
                    Node.from_uri(enode) for enode in ROPSTEN_BOOTNODES
                )
        else:
            self.bootstrap_nodes = bootstrap_nodes

        # validation
        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")

        # set values
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            self.data_dir = get_data_dir_for_network_id(self.network_id)

        if nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

    @property
    def data_dir(self) -> PurePath:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.  All other chain directories are by
        default relative to this directory.
        """
        return self._data_dir

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = PurePath(os.path.abspath(value))

    @property
    def database_dir(self) -> str:
        if self.sync_mode == SYNC_FULL:
            return str(self.data_dir / DATABASE_DIR_NAME / "full")
        elif self.sync_mode == SYNC_LIGHT:
            return str(self.data_dir / DATABASE_DIR_NAME / "light")
        else:
            raise ValueError("Unknown sync mode: {}}".format(self.sync_mode))

    @property
    def database_ipc_path(self) -> str:
        return get_database_socket_path(self.data_dir)

    @property
    def jsonrpc_ipc_path(self) -> str:
        return get_jsonrpc_socket_path(self.data_dir)

    @property
    def nodekey_path(self) -> PurePath:
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.data_dir)
        else:
            return self._nodekey_path

    @nodekey_path.setter
    def nodekey_path(self, value: str) -> None:
        self._nodekey_path = PurePath(os.path.abspath(value))

    @property
    def nodekey(self) -> PrivateKey:
        if self._nodekey is None:
            try:
                return load_nodekey(self.nodekey_path)
            except FileNotFoundError:
                # no file at the nodekey_path so we have a null nodekey
                return None
        else:
            if isinstance(self._nodekey, bytes):
                return keys.PrivateKey(self._nodekey)
            elif isinstance(self._nodekey, PrivateKey):
                return self._nodekey
            return self._nodekey

    @nodekey.setter
    def nodekey(self, value: Union[bytes, PrivateKey]) -> None:
        if isinstance(value, bytes):
            self._nodekey = keys.PrivateKey(value)
        elif isinstance(value, PrivateKey):
            self._nodekey = value
        else:
            raise TypeError(
                "Nodekey must either be a raw byte-string or an eth_keys "
                "`PrivateKey` instance"
            )

    @classmethod
    def from_parser_args(cls, parser_args):
        constructor_kwargs = construct_chain_config_params(parser_args)
        return cls(**constructor_kwargs)


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
