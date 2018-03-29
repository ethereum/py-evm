import json
import os

from cytoolz import (
    dissoc,
)

from eth_utils import (
    decode_hex,
    to_dict,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from evm.chains.mainnet import (
    MAINNET_GENESIS_PARAMS,
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_GENESIS_PARAMS,
    ROPSTEN_NETWORK_ID,
)
from evm.rlp.headers import BlockHeader

from .genesis import (
    normalize_genesis_params,
)
from .xdg import (
    get_xdg_trinity_root,
)

from typing import Union


DEFAULT_DATA_DIRS = {
    ROPSTEN_NETWORK_ID: 'ropsten',
    MAINNET_NETWORK_ID: 'mainnet',
}
PRECONFIGURED_NETWORKS = {
    MAINNET_NETWORK_ID: MAINNET_GENESIS_PARAMS,
    ROPSTEN_NETWORK_ID: ROPSTEN_GENESIS_PARAMS,
}


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str) -> str:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(get_xdg_trinity_root(), chain_name),
    )


def get_data_dir_for_network_id(network_id: int) -> str:
    """
    Returns the data directory for the chain associated with the given network
    id.  If the network id is unknown, raises a KeyError.
    """
    try:
        return get_local_data_dir(DEFAULT_DATA_DIRS[network_id])
    except KeyError:
        raise KeyError("Unknown network id: `{0}`".format(network_id))


DATABASE_DIR_NAME = 'chain'


def get_database_dir(data_dir: str) -> str:
    """
    Returns the directory path where chain data will be stored.
    """
    return os.path.join(data_dir, DATABASE_DIR_NAME)


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(data_dir: str) -> str:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return os.environ.get(
        'TRINITY_NODEKEY',
        os.path.join(data_dir, NODEKEY_FILENAME),
    )


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(data_dir: str) -> str:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return os.environ.get(
        'TRINITY_DATABASE_IPC',
        os.path.join(data_dir, DATABASE_SOCKET_FILENAME),
    )


JSONRPC_SOCKET_FILENAME = 'jsonrpc.ipc'


def get_jsonrpc_socket_path(data_dir: str) -> str:
    """
    Returns the path to the ipc socket for the JSON-RPC server.
    """
    return os.environ.get(
        'TRINITY_JSONRPC_IPC',
        os.path.join(data_dir, JSONRPC_SOCKET_FILENAME),
    )


#
# Nodekey loading
#
def load_nodekey(nodekey_path: str) -> PrivateKey:
    with open(nodekey_path, 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


#
# ChainConfig class
#
class ChainConfig:
    _data_dir = None
    _nodekey_path = None
    _nodekey = None
    _network_id = None
    _genesis_params = None

    def __init__(self,
                 network_id: int,
                 data_dir: str=None,
                 nodekey_path: str = None,
                 nodekey: PrivateKey = None,
                 genesis_params: dict = None) -> None:
        self.network_id = network_id

        # validation
        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")

        # set values
        if data_dir is not None:
            self.data_dir = data_dir
        elif self.network_id in PRECONFIGURED_NETWORKS:
            self.data_dir = get_data_dir_for_network_id(self.network_id)
        else:
            raise ValueError(
                "Unable to determine data_dir.  Please provide an explicit path "
                "with --data-dir"
            )

        if nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

        if genesis_params is not None:
            self._genesis_params = genesis_params

    @property
    def is_preconfigured_network(self):
        return self.network_id in PRECONFIGURED_NETWORKS

    @property
    def has_genesis_params(self):
        return self._genesis_params is not None or self.is_preconfigured_network

    @property
    def genesis_params(self):
        if self._genesis_params is not None:
            return self._genesis_params
        elif self.is_preconfigured_network:
            return PRECONFIGURED_NETWORKS[self.network_id]
        else:
            raise AttributeError(
                "No genesis parameters were provided and network_id is not for "
                "a preconfigured network"
            )

    @property
    def genesis_header(self):
        params = dissoc(self.genesis_params, 'alloc', 'config')
        # TODO: handle custom alloc AND mainnet alloc
        # TODO: handle custom config
        return BlockHeader(**params)

    @property
    def genesis_state(self):
        if 'alloc' in self.genesis_params:
            return self.genesis_params['alloc']
        else:
            raise NotImplementedError(
                "TODO: not yet implemented, need to reference mainnet genesis alloc here"
            )

    @property
    def data_dir(self) -> str:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.  All other chain directories are by
        default relative to this directory.
        """
        return self._data_dir

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = os.path.abspath(value)

    @property
    def database_dir(self) -> str:
        return get_database_dir(self.data_dir)

    @property
    def database_ipc_path(self) -> str:
        return get_database_socket_path(self.data_dir)

    @property
    def jsonrpc_ipc_path(self) -> str:
        return get_jsonrpc_socket_path(self.data_dir)

    @property
    def nodekey_path(self) -> str:
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.data_dir)
        else:
            return self._nodekey_path

    @nodekey_path.setter
    def nodekey_path(self, value: str) -> None:
        self._nodekey_path = os.path.abspath(value)

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
    elif args.genesis is not None:
        if os.path.exists(args.genesis):
            with open(args.genesis) as genesis_file:
                raw_genesis_params = json.load(genesis_file)
                genesis_params = normalize_genesis_params(raw_genesis_params)
            yield 'genesis_params', genesis_params
        elif isinstance(args.genesis, str):
            try:
                raw_genesis_params = json.loads(args.genesis)
                genesis_params = normalize_genesis_params(raw_genesis_params)
                yield 'genesis_params', genesis_params
            except json.JSONDecodeError:
                raise ValueError(
                    "Unable to parse provided genesis json: {0}".format(args.genesis)
                )
        else:
            raise TypeError(
                "Genesis data must be either a filesystem path or a JSON "
                "string.  Got {0}".format(type(args.genesis))
            )
