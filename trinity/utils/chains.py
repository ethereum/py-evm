import os

from cytoolz import (
    get_in,
)

from eth_utils import (
    decode_hex,
    to_dict,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from trinity.constants import (
    ROPSTEN,
)
from .xdg import (
    get_xdg_trinity_root,
)

from typing import Union


#
# Filesystem path utils
#
def get_default_data_dir(chain_identifier: str) -> str:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(get_xdg_trinity_root(), chain_identifier),
    )


DATABASE_DIR_NAME = 'chain'


def get_database_dir(chain_identifier: str, data_dir: str=None) -> str:
    """
    Returns the directory path where chain data will be stored.
    """
    if data_dir is None:
        data_dir = get_default_data_dir(chain_identifier)
    return os.path.join(data_dir, DATABASE_DIR_NAME)


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(chain_identifier: str, data_dir: str=None) -> str:
    """
    Returns the path to the private key used for devp2p connections.
    """
    if data_dir is None:
        data_dir = get_default_data_dir(chain_identifier)
    return os.environ.get(
        'TRINITY_NODEKEY',
        os.path.join(data_dir, NODEKEY_FILENAME),
    )


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(chain_identifier: str, data_dir: str=None) -> str:
    """
    Returns the path to the private key used for devp2p connections.
    """
    if data_dir is None:
        data_dir = get_default_data_dir(chain_identifier)
    return os.environ.get(
        'TRINITY_DATABASE_IPC',
        os.path.join(data_dir, DATABASE_SOCKET_FILENAME),
    )


#
# Nodekey loading
#
def load_nodekey(nodekey_path: str) -> PrivateKey:
    with open(nodekey_path, 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


# TODO: move this somewhere more appropriate
CHAIN_CONFIG_DEFAULTS = {
    ROPSTEN: {
        'network_id': ROPSTEN_NETWORK_ID,
    }
}


class ChainConfig:
    chain_identifier = None

    _data_dir = None
    _nodekey_path = None
    _nodekey = None
    _network_id = None

    def __init__(self,
                 chain_identifier: str,
                 data_dir: str=None,
                 nodekey_path: str=None,
                 nodekey: PrivateKey=None,
                 network_id: int=None) -> None:
        # validation
        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")

        # set values
        self.chain_identifier = chain_identifier

        if data_dir is not None:
            self.data_dir = data_dir

        if nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

    @property
    def data_dir(self) -> str:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.  All other chain directories are by
        default relative to this directory.
        """
        if self._data_dir is None:
            return get_default_data_dir(self.chain_identifier)
        else:
            return self._data_dir

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = os.path.abspath(value)

    @property
    def database_dir(self) -> str:
        return get_database_dir(self.chain_identifier, self.data_dir)

    @property
    def database_ipc_path(self) -> str:
        return get_database_socket_path(self.chain_identifier, self.data_dir)

    @property
    def nodekey_path(self) -> str:
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.chain_identifier, self.data_dir)
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

    @property
    def network_id(self) -> int:
        if self._network_id is not None:
            return self._network_id

        try:
            return get_in(
                [self.chain_identifier, 'network_id'],
                CHAIN_CONFIG_DEFAULTS,
                no_default=True,
            )
        except KeyError:
            raise ValueError(
                "The network_id for the chain '{0}' was not explicitely set and "
                "is not for a known network.  Please specify a network_id"
            )

    @classmethod
    def from_parser_args(cls, chain_identifier, parser_args):
        constructor_kwargs = construct_chain_config_params(parser_args)
        return cls(chain_identifier, **constructor_kwargs)


@to_dict
def construct_chain_config_params(args):
    """
    Helper function for constructing the kwargs to initialize a ChainConfig object.
    """
    if args.data_dir is not None:
        yield 'data_dir', args.data_dir

    if args.nodekey_path and args.nodekey:
        raise ValueError("Cannot provide both nodekey_path and nodekey")
    elif args.nodekey_path is not None:
        yield 'nodekey_path', args.nodekey_path
    elif args.nodekey is not None:
        yield 'nodekey', decode_hex(args.nodekey)
