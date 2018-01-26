import os

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from .xdg import (
    get_xdg_trinity_home,
)


def get_base_dir(chain_identifier):
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return os.environ.get(
        'TRINITY_BASE_DIR',
        os.path.join(get_xdg_trinity_home(), chain_identifier),
    )


DATA_DIR_NAME = 'chain'


def get_data_dir(chain_identifier, base_dir=None):
    """
    Returns the directory path where chain data will be stored.
    """
    if base_dir is None:
        base_dir = get_base_dir(chain_identifier)
    return os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(base_dir, DATA_DIR_NAME),
    )


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(chain_identifier, base_dir=None):
    """
    Returns the path to the private key used for devp2p connections.
    """
    if base_dir is None:
        base_dir = get_base_dir(chain_identifier)
    return os.environ.get(
        'TRINITY_NODEKEY',
        os.path.join(base_dir, NODEKEY_FILENAME),
    )


def load_nodekey(nodekey_path):
    with open(nodekey_path, 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


class ChainConfig:
    chain_identifier = None

    _base_dir = None
    _data_dir = None
    _nodekey_path = None
    _nodekey = None

    def __init__(self,
                 chain_identifier,
                 base_dir=None,
                 data_dir=None,
                 nodekey_path=None,
                 nodekey=None):
        # validation
        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")

        # set values
        self.chain_identifier = chain_identifier

        if base_dir is not None:
            self.base_dir = base_dir

        if data_dir is not None:
            self.data_dir = data_dir

        if nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

    @property
    def base_dir(self):
        if self._base_dir is None:
            return get_base_dir(self.chain_identifier)
        else:
            return self._base_dir

    @base_dir.setter
    def base_dir(self, value):
        self._base_dir = os.path.abspath(value)

    @property
    def data_dir(self):
        if self._data_dir is None:
            return get_data_dir(self.chain_identifier, self.base_dir)
        else:
            return self._data_dir

    @data_dir.setter
    def data_dir(self, value):
        self._data_dir = os.path.abspath(value)

    @property
    def nodekey_path(self):
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.chain_identifier, self.base_dir)
        else:
            return self._nodekey_path

    @nodekey_path.setter
    def nodekey_path(self, value):
        self._nodekey_path = os.path.abspath(value)

    @property
    def nodekey(self):
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
    def nodekey(self, value):
        if isinstance(value, bytes):
            self._nodekey = keys.PrivateKey(value)
        elif isinstance(value, PrivateKey):
            self._nodekey = value
        else:
            raise TypeError(
                "Nodekey must either be a raw byte-string or an eth_keys "
                "`PrivateKey` instance"
            )
